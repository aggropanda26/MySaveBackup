from pathlib import Path
import json
import os
import re
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QProgressBar, QPlainTextEdit, QInputDialog)
from .core import Game, discover, backup, inspect_backup
from .covers import CoverLoader, cover_app_id, valid_app_id

PROJECT = Path(__file__).resolve().parent.parent

class Worker(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
    def run(self):
        try:
            self.result.emit(self.operation(self.progress.emit))
        except Exception as exc:
            self.failed.emit(str(exc))

class Window(QMainWindow):
    def __init__(self, config_dir=None):
        super().__init__()
        self.setWindowTitle('MySaveBackup · Spielstände sichern')
        icon_path = PROJECT/'assets/icon.png'
        if not icon_path.is_file(): icon_path = PROJECT/'icon.png'
        self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1080, 760)
        self.games = []; self.worker = None; self.last_backup = None
        self.config = Path(config_dir) if config_dir is not None else Path.home()/'.config/mysavebackup'
        self.first_start_marker = self.config/'first-start-dismissed'
        self.manual_file = self.config/'manual-sources.json'
        self.mode = ''
        self.cover_overrides_file = self.config/'cover-ids.json'
        try:
            self.cover_overrides = json.loads(self.cover_overrides_file.read_text())
            if not isinstance(self.cover_overrides, dict): self.cover_overrides = {}
        except (OSError, ValueError):
            self.cover_overrides = {}
        cache = (self.config/'cache' if config_dir is not None else
                 Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'mysavebackup')
        self.cover_loader = CoverLoader(cache/'covers', self)
        self.cover_loader.ready.connect(self.cover_ready)
        self.cover_loader.unavailable.connect(self.cover_unavailable)
        self.cover_items = {}
        placeholder = QPixmap(56, 84); placeholder.fill(QColor('#27354a'))
        painter = QPainter(placeholder); painter.setPen(QColor('#b8c9e0'))
        painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, 'Kein\nCover'); painter.end()
        self.cover_placeholder = QIcon(placeholder)
        body = QWidget(); self.setCentralWidget(body); layout = QVBoxLayout(body)
        title = QLabel('MySaveBackup'); title.setStyleSheet('font-size: 28px; font-weight: 700;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Spielstände sichern. Kopien prüfen. Originale behalten.'))
        self.first_start_banner = QWidget()
        banner_layout = QHBoxLayout(self.first_start_banner)
        banner_layout.addWidget(QLabel('Sorry nur Ki Slop'))
        banner_layout.addStretch()
        self.dismiss_first_start_button = QPushButton('Schließen')
        self.dismiss_first_start_button.clicked.connect(self.dismiss_first_start)
        banner_layout.addWidget(self.dismiss_first_start_button)
        self.first_start_banner.setVisible(not self.first_start_marker.exists())
        layout.addWidget(self.first_start_banner)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self.scan_button = QPushButton('Spiele suchen'); self.scan_button.clicked.connect(self.scan); bar.addWidget(self.scan_button)
        self.manual_button = QPushButton('Spielstandordner hinzufügen'); self.manual_button.clicked.connect(self.add_manual); bar.addWidget(self.manual_button)
        self.open_source_button = QPushButton('Originalordner öffnen'); self.open_source_button.clicked.connect(self.open_source); bar.addWidget(self.open_source_button)
        self.assign_cover_button = QPushButton('Cover zuordnen'); self.assign_cover_button.clicked.connect(self.assign_cover); bar.addWidget(self.assign_cover_button)
        bar.addStretch()
        self.search = QLineEdit(); self.search.setPlaceholderText('Spiele filtern …'); self.search.textChanged.connect(self.filter); layout.addWidget(self.search)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(['Spiel / Spielstandordner', 'Status'])
        self.tree.setIconSize(QSize(56, 84))
        self.tree.itemClicked.connect(self.open_clicked_source)
        self.tree.setColumnWidth(0, 730); self.tree.setRootIsDecorated(True); layout.addWidget(self.tree, 1)
        target = QHBoxLayout(); layout.addLayout(target)
        target.addWidget(QLabel('Backup-Ziel:'))
        self.destination = QLineEdit(str(Path.home()/'Dokumente/MySaveBackup'))
        target.addWidget(self.destination, 1)
        self.browse_button = QPushButton('Ordner wählen'); self.browse_button.clicked.connect(self.choose_target); target.addWidget(self.browse_button)
        actions = QHBoxLayout(); layout.addLayout(actions)
        self.backup_button = QPushButton('Ausgewählte Spiele sichern'); self.backup_button.clicked.connect(self.make_backup); actions.addWidget(self.backup_button)
        self.verify_button = QPushButton('Backup und Duplikate prüfen'); self.verify_button.clicked.connect(self.verify); actions.addWidget(self.verify_button)
        self.open_backup_button = QPushButton('Letztes Backup öffnen'); self.open_backup_button.clicked.connect(self.open_backup); self.open_backup_button.setEnabled(False); actions.addWidget(self.open_backup_button)
        self.status = QLabel('Bereit. Klicke auf „Spiele suchen“.'); layout.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.setRange(0,1); self.progress.setValue(0); layout.addWidget(self.progress)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(165); layout.addWidget(self.log)
        footer = QLabel('Version 0.1 · Originale werden nur gelesen. Duplikatprüfung zeigt eine Vorschau und löscht nichts.')
        footer.setWordWrap(True); layout.addWidget(footer)

    def dismiss_first_start(self):
        # Dismiss immediately, even if remembering the choice fails.
        self.first_start_banner.hide()
        try:
            self.config.mkdir(parents=True, exist_ok=True)
            self.first_start_marker.touch(exist_ok=True)
        except OSError:
            self.log.appendPlainText('Der Hinweis wurde geschlossen, konnte aber nicht dauerhaft ausgeblendet werden.')

    def busy(self, value):
        for widget in (self.scan_button,self.manual_button,self.backup_button,self.verify_button,self.browse_button,self.assign_cover_button,self.destination,self.tree):
            widget.setEnabled(not value)
        self.progress.setRange(0,0 if value else 1)
        if not value: self.progress.setValue(1)

    def start(self, mode, operation):
        if self.worker is not None:
            return
        self.mode = mode; self.busy(True)
        worker = Worker(operation, self); self.worker = worker
        worker.result.connect(self.completed); worker.failed.connect(self.failed)
        worker.progress.connect(self.update_status); worker.finished.connect(self.finished)
        worker.start()

    @Slot(str)
    def update_status(self, text):
        self.status.setText(text)

    @Slot()
    def finished(self):
        old = self.worker; self.worker = None
        self.busy(False)
        if old: old.deleteLater()

    @Slot(str)
    def failed(self, message):
        self.status.setText('Vorgang nicht vollständig abgeschlossen.')
        self.log.appendPlainText('FEHLER: '+message)
        QMessageBox.warning(self, 'Vorgang fehlgeschlagen', message)

    @Slot(object)
    def completed(self, result):
        if self.mode == 'scan':
            self.games = result; self.populate()
            ready = sum(bool(g.sources) for g in self.games)
            self.status.setText(f'{len(self.games)} Spiele · {ready} mit gefundenen Spielstanddateien')
            self.log.appendPlainText('Suche abgeschlossen. Nicht erkannte Speicherorte kannst du manuell ergänzen.')
        elif self.mode == 'backup':
            self.last_backup = Path(result); self.open_backup_button.setEnabled(True)
            self.status.setText('Backup erstellt und alle Kopien geprüft.')
            self.log.appendPlainText(f'Gesichert: {result}')
        else:
            self.status.setText(f"{result['files']} Dateien · {len(result['duplicates'])} identische Duplikate · {len(result['errors'])} Prüffehler")
            self.log.appendPlainText('Backup-Status: '+result['status'])
            for error in result['errors']: self.log.appendPlainText(error)
            for duplicate in result['duplicates']:
                self.log.appendPlainText(f"Identisch: {duplicate['copy']}\n  Entspricht: {duplicate['keep']}")
            self.log.appendPlainText('Prüfung abgeschlossen. Keine Dateien verändert.')

    def scan(self):
        def work(progress):
            progress('Suche Steam-Bibliotheken und bekannte Spielstandordner …')
            games = discover(PROJECT/'local_sources.json')
            if self.manual_file.exists():
                for item in json.loads(self.manual_file.read_text()):
                    match = next((g for g in games if g.name == item['name']), None)
                    sources = [Path(p) for p in item['sources'] if Path(p).exists()]
                    if match:
                        match.sources = list(dict.fromkeys(match.sources+sources))
                    else: games.append(Game(item['name'],sources))
            return sorted(games,key=lambda g:g.name.casefold())
        self.start('scan',work)

    def populate(self):
        self.cover_items = {}
        self.tree.clear()
        for g in self.games:
            item = QTreeWidgetItem([g.name, f'{len(g.sources)} Speicherorte' if g.sources else 'Kein lokaler Spielstand erkannt'])
            item.setData(0,Qt.ItemDataRole.UserRole,g)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0,Qt.CheckState.Checked if g.sources else Qt.CheckState.Unchecked)
            item.setIcon(0, self.cover_placeholder)
            app_id = cover_app_id(g, self.cover_overrides)
            if app_id:
                item.setToolTip(0, f'Cover wird im Hintergrund geladen · Steam-App {app_id}')
                self.cover_items.setdefault(app_id, []).append(item)
            else:
                item.setToolTip(0, 'Keine Steam-App-ID bekannt. Über „Cover zuordnen“ ergänzen.')
            self.tree.addTopLevelItem(item)
            for source in g.sources:
                child = QTreeWidgetItem([str(source),'Original · nur lesen'])
                child.setData(0,Qt.ItemDataRole.UserRole,str(source))
                child.setToolTip(0, 'Einmal klicken, um diesen Ordner im Dateimanager zu öffnen.')
                font = child.font(0); font.setUnderline(True); child.setFont(0, font)
                item.addChild(child)
        self.filter(self.search.text())
        for app_id in self.cover_items:
            self.cover_loader.request(app_id)

    def cover_ready(self, app_id, image):
        icon = QIcon(QPixmap.fromImage(image))
        for item in self.cover_items.get(app_id, []):
            item.setIcon(0, icon)
            item.setToolTip(0, f'Cover von Steam · App {app_id}')

    def cover_unavailable(self, app_id):
        for item in self.cover_items.get(app_id, []):
            item.setToolTip(0, f'Cover momentan nicht verfügbar · Steam-App {app_id}. Bei der nächsten App-Sitzung wird erneut versucht.')

    def assign_cover(self):
        item = self.tree.currentItem()
        if item is None:
            self.status.setText('Bitte zuerst ein Spiel auswählen.'); return
        if item.parent() is not None: item = item.parent()
        game = item.data(0, Qt.ItemDataRole.UserRole)
        value, ok = QInputDialog.getText(self, 'Cover zuordnen',
            'Steam-App-ID oder SteamDB-Link zum Spiel:',
            text=cover_app_id(game, self.cover_overrides))
        if not ok: return
        value = value.strip()
        match = re.fullmatch(r'https://(?:steamdb.info|store.steampowered.com)/app/([0-9]+)(?:/[^?#]*)?(?:[?#].*)?', value)
        app_id = match.group(1) if match else value
        if not valid_app_id(app_id):
            QMessageBox.information(self, 'Ungültige App-ID', 'Bitte eine numerische Steam-App-ID oder einen SteamDB-Spiellink eingeben.'); return
        try:
            self.config.mkdir(parents=True, exist_ok=True)
            overrides = dict(self.cover_overrides); overrides[game.name] = app_id
            temporary = self.cover_overrides_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(overrides, ensure_ascii=False, indent=2))
            temporary.replace(self.cover_overrides_file)
            self.cover_overrides = overrides
            self.cover_loader.failed.discard(app_id)
            # Update only this item's artwork; preserve checkboxes, expansion and selection.
            for key in list(self.cover_items):
                self.cover_items[key] = [entry for entry in self.cover_items[key] if entry is not item]
            self.cover_items.setdefault(app_id, []).append(item)
            item.setIcon(0, self.cover_placeholder)
            self.cover_loader.request(app_id)
        except OSError as exc:
            self.failed(str(exc))

    def filter(self, text):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i); item.setHidden(text.casefold() not in item.text(0).casefold())

    def choose_target(self):
        folder = QFileDialog.getExistingDirectory(self,'Backup-Ziel wählen',self.destination.text())
        if folder: self.destination.setText(folder)

    def make_backup(self):
        selected=[]
        for i in range(self.tree.topLevelItemCount()):
            item=self.tree.topLevelItem(i)
            if item.checkState(0)==Qt.CheckState.Checked:
                game=item.data(0,Qt.ItemDataRole.UserRole)
                if game.sources: selected.append(game)
        if not selected:
            QMessageBox.information(self,'Keine Auswahl','Bitte ein Spiel mit gefundenen Spielstanddateien auswählen.'); return
        if not self.destination.text().strip():
            QMessageBox.information(self,'Backup-Ziel','Bitte einen Zielordner auswählen.'); return
        destination=Path(self.destination.text())
        self.start('backup',lambda progress:backup(selected,destination,progress))

    def verify(self):
        folder=QFileDialog.getExistingDirectory(self,'Backup-Ordner mit manifest.json wählen',str(self.last_backup or self.destination.text()))
        if folder: self.start('verify',lambda progress:inspect_backup(Path(folder)))

    def open_backup(self):
        if self.last_backup: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_backup)))

    def open_clicked_source(self, item, column):
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if column == 0 and isinstance(value, str):
            self.open_source_path(Path(value))

    def open_source_path(self, path):
        if not path.exists():
            self.status.setText(f'Ordner nicht verfügbar: {path}')
            return
        folder = path if path.is_dir() else path.parent
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            self.status.setText(f'Dateimanager konnte nicht geöffnet werden: {folder}')

    def open_source(self):
        item=self.tree.currentItem()
        if not item:return
        value=item.data(0,Qt.ItemDataRole.UserRole)
        if isinstance(value,Game):
            if len(value.sources)!=1:
                item.setExpanded(True)
                self.status.setText('Wähle unter dem Spiel den gewünschten Originalordner aus.');return
            path=value.sources[0]
        else:path=Path(value)
        self.open_source_path(path)

    def add_manual(self):
        name,ok=QInputDialog.getText(self,'Spiel hinzufügen','Name des Spiels:')
        if not ok or not name.strip():return
        folder=QFileDialog.getExistingDirectory(self,'Spielstandordner wählen')
        if not folder:return
        try:
            self.config.mkdir(parents=True,exist_ok=True)
            data=json.loads(self.manual_file.read_text()) if self.manual_file.exists() else []
            data.append({'name':name.strip(),'sources':[folder]})
            temporary=self.manual_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)); temporary.replace(self.manual_file)
            self.scan()
        except Exception as exc:self.failed(str(exc))

    def closeEvent(self,event):
        if self.worker is not None:
            QMessageBox.information(self,'Vorgang läuft','Bitte warte, bis die laufende Suche oder Sicherung abgeschlossen ist.')
            event.ignore()
        else:
            self.cover_loader.close()
            event.accept()

def main():
    app=QApplication([]); app.setApplicationName('MySaveBackup')
    app.setDesktopFileName('mysavebackup')
    window=Window(); app.setWindowIcon(window.windowIcon()); window.show(); app.exec()
