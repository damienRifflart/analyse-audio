from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel, QMessageBox
import pyaudio, math, sys, numpy as np, struct, pyqtgraph as pg, wave

class AudioStream(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()        

        # tabs
        self.tab_widget = QTabWidget()
        
        self.acquisitionTab = QWidget()
        self.analyseTab = QWidget()
        self.parametreTab = QWidget()
        self.fichierTab = QWidget()

        self.tab_widget.addTab(self.acquisitionTab, "Acquisition")
        self.tab_widget.addTab(self.analyseTab, "Analyse")
        self.tab_widget.addTab(self.fichierTab, "Fichier")
        self.tab_widget.addTab(self.parametreTab, "Paramètres")

        # https://people.csail.mit.edu/hubert/pyaudio/docs/#pyaudio.PyAudio.open
        # parametres prise du son
        self.chunk = 1024 # divise le flux en petit blocs de 1024 échantillons (= mesure de l'amplitude à un instant donné)
        self.format = pyaudio.paInt16  # chaque échantillon est codé sur 16 bits (2 octets)
        self.channels = 1  # 1 = mono (son n'est pas spatiale) / 2 = stéréo
        self.rate = 44100  # taux d'échantillonnage (Hz) : nombre d'échantillons capturés par secondes
                           # ici, 44 100 échantillons par seconde, donc chaque échantillon représente 1 / 44100 = ~22.7 µs de son
        self.audio = pyaudio.PyAudio()  # création de l'objet PyAudio: gère l'entrée audio

        # flux audio
        self.stream = self.audio.open(
            format = self.format, 
            channels = self.channels,
            rate = self.rate,
            frames_per_buffer = self.chunk,
            input = True # spécifie que le flux doit capturer de l'audio (input=entré)
        )

        # button pause
        self.pause_state = False
        self.pause_btn = QtWidgets.QPushButton("Pause ⏸️")
        self.pause_btn.clicked.connect(self.pause)
        self.pause_btn.setFixedWidth(100)

        layout = QtWidgets.QVBoxLayout(self) # créé un layout vertical
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.tab_widget)

        # paramètres analyse après fft
        self.fundamental_freqs = {'live': [], 'file': []}
        self.fundamental_freq = {'live': None, 'file': None}
        self.fundamental_label = {'live': '', 'file': ''}
        self.min_freq = 250
        self.max_freq = 1100

        self.tab_widget.currentChanged.connect(self.on_tab_change)

        self.initTabAcquisition()
        self.initTabAnalyse()
        self.initTabFichier()
        self.initTabParametres()

    def freq_to_note(self, freq):
        # https://stackoverflow.com/questions/64505024/turning-frequencies-into-notes-in-python
        notes = ['La', 'La#', 'Si', 'Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#']
        note_number = 12 * math.log2(freq / 440) + 49  
        note_number = round(note_number)
        note = (note_number - 1 ) % len(notes)
        note = notes[note]
        octave = (note_number + 8 ) // len(notes)
        return f"{note}{octave}"

    def on_tab_change(self, index):
        current_tab = self.tab_widget.tabText(index)
        if current_tab == "Acquisition" or current_tab == "Analyse":
            self.timer.start()
        else:
            self.timer.stop()

    def createPlotWidget(self, x_label="", y_label="Amplitude (UA)"):
        # https://pyqtgraph.readthedocs.io/en/latest/getting_started/plotting.html
        # graphique
        plot = pg.PlotWidget() # composant de PyQtGraph: permet d'afficher des graphiques 2D
        plot.setYRange(-4000, 4000) # comme c'est codé sur 16 bits: 2^15 = 32 768. Les valeurs vont de -32 768 au min à 32 767 au max
        plot.setLabel("bottom", x_label)
        plot.setLabel("left", y_label)
        return plot

    def initTabAcquisition(self):
        layout = QVBoxLayout(self.acquisitionTab)
        plot = self.createPlotWidget(x_label="Temps (s)")
        self.curve_acquisition = plot.plot(pen='cyan')  # on plot une ligne ou courbe qui contiendra les valeurs

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_acquisition)
        self.timer.timeout.connect(self.update_analyse)
        self.timer.start(30) # toutes les 30ms

        layout.addWidget(plot)

    def initTabAnalyse(self):
        layout = QtWidgets.QHBoxLayout(self.analyseTab)
        plot = self.createPlotWidget(x_label="Fréquences (Hz)")
        self.curve_analyse = plot.plot(pen='cyan')# on plot une ligne ou courbe qui contiendra les valeurs

        # ligne pour la fréquence minimale
        self.min_freq_line = pg.InfiniteLine(self.min_freq, angle=90, pen=pg.mkPen('g', width=2))
        plot.addItem(self.min_freq_line)

        # ligne pour la fréquence maximale
        self.max_freq_line = pg.InfiniteLine(self.max_freq, angle=90, pen=pg.mkPen('y', width=2))
        plot.addItem(self.max_freq_line)

        # panel à droite pour afficher les fréquences détéctées
        # https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QVBoxLayout.html
        self.freq_panel = QWidget() # créé un widget pour montrer les fréquences
        freq_layout = QVBoxLayout(self.freq_panel)
        self.fundamental_label['live'] = QLabel(f"Fréquence fondamentale détéctée: \n {self.fundamental_freq['live']}")
        self.fundamental_label['live'].setAlignment(QtCore.Qt.AlignCenter)
        self.fundamental_label['live'].setStyleSheet("font-size: 30px;")
        freq_layout.addWidget(self.fundamental_label['live']) # ajoute le label au layout

        generate_sound_btn = QtWidgets.QPushButton("Générer le son")
        generate_sound_btn.clicked.connect(lambda: self.generate_sound('live'))
        freq_layout.addWidget(generate_sound_btn)
    
        layout.addWidget(plot, stretch=2) # prend 2/3 du tab
        layout.addWidget(self.freq_panel, stretch=1) # prend 1/3 du tab

    def initTabFichier(self):
        layout = QtWidgets.QVBoxLayout(self.fichierTab) # layout vertical

        # boutton pour ouvrir un fichier
        open_file_btn = QtWidgets.QPushButton("Ouvrir un fichier audio")
        open_file_btn.clicked.connect(self.open_file_dialog)
        layout.addWidget(open_file_btn)

        # horizontal layout for plot and frequency panel
        h_layout = QtWidgets.QHBoxLayout()
        
        plot = self.createPlotWidget(x_label="Fréquences (Hz)")
        self.file_curve = plot.plot(pen='cyan') # on plot une ligne ou courbe qui contiendra les valeurs
        
        self.freq_panel_file = QWidget() # créé un widget pour montrer les fréquences
        freq_layout = QVBoxLayout(self.freq_panel_file) # créé un layout vertical pour le widget
        self.fundamental_label['file'] = QLabel(f"Fréquence fondamentale détéctée: \n {self.fundamental_freq['file']}")
        self.fundamental_label['file'].setAlignment(QtCore.Qt.AlignCenter)
        self.fundamental_label['file'].setStyleSheet("font-size: 30px;")
        freq_layout.addWidget(self.fundamental_label['file']) # ajoute le label au layout

        generate_sound_btn = QtWidgets.QPushButton("Générer le son")
        generate_sound_btn.clicked.connect(lambda: self.generate_sound('file'))
        freq_layout.addWidget(generate_sound_btn)
    
        h_layout.addWidget(plot, stretch=2) # prend 2/3 du tab
        h_layout.addWidget(self.freq_panel_file, stretch=1) # prend 1/3 du tab

        layout.addLayout(h_layout)

    def initTabParametres(self):
        layout = QVBoxLayout(self.parametreTab)

        # https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QSlider.html
        # slider pour la fréquence minimale
        self.min_freq_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.min_freq_slider.setMinimum(0)
        self.min_freq_slider.setMaximum(3000)
        self.min_freq_slider.setValue(self.min_freq)
        self.min_freq_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.min_freq_slider.setTickInterval(100)
        self.min_freq_slider.valueChanged.connect(self.update_min_freq)

        # slider pour la fréquence maximale
        self.max_freq_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.max_freq_slider.setMinimum(0)
        self.max_freq_slider.setMaximum(3000)
        self.max_freq_slider.setValue(self.max_freq)
        self.max_freq_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.max_freq_slider.setTickInterval(100)
        self.max_freq_slider.valueChanged.connect(self.update_max_freq)

        layout.addWidget(QLabel("Fréquence minimale"))
        layout.addWidget(self.min_freq_slider)
        layout.addWidget(QLabel("Fréquence maximale"))
        layout.addWidget(self.max_freq_slider)

    def process_audio_data(self, data, data_type='int16'):
        # conversion des données en un tableau lisible par Numpy
        # data est une séquence d'octets au format binaire, que Numpy ne peut pas directement traiter.
        # struct.unpack convertit ces octets en valeurs numériques (ex. : 7, -8, 11)

        # https://docs.python.org/3/library/struct.html#struct.unpack
        # on récupère le nombre d'octets: 1024 échantillons codés sur 16 bits (2 octets), donc 1024 * 2 = 2048 octets
        # on rajoute B pour byte ou octet en français, ça permet de préciser à la fonction unpack que ce sont 2048 octets
        num_octets = f"{2 * self.chunk}B"
        unpacked_data = struct.unpack(num_octets, data)

        # une fois qu'on a des valeurs numériques, il faut les convertir en un tableau Numpy (de type data_type bits)
        data_table = np.array(unpacked_data, dtype=getattr(np, data_type))
        return data_table[::2]  # slice le tableau pour prendre qu'un élement sur deux (=> flux mono). Syntaxe: sequence[start:end:step]

    def analyse_fft(self, data_table, mode='live'):
        # transformée de Fourier (FFT)
        # https://numpy.org/doc/2.1/reference/generated/numpy.fft.rfft.html
        # on utilise rfft car data contient des nombres réels (pas complexes).
        fft_data = np.abs(np.fft.rfft(data_table))

        # calcul des fréquences correspondantes
        # shttps://numpy.org/doc/2.1/reference/generated/numpy.fft.rfftfreq.html
        # rfftfreq génère un tableau contenant les fréquences correspondantes aux données FFT.
        freqs = np.fft.rfftfreq(len(data_table), d=1/self.rate)
        
        # filtrage des fréquences (masque)
        freq_mask = (freqs >= self.min_freq) & (freqs <= self.max_freq)
        # filtrer les données FFT et les fréquences correspondantes
        filtered_fft = fft_data[freq_mask]
        filtered_freqs = freqs[freq_mask]
        
        # calcul du bruit moyen
        if len(filtered_fft) > 0:
            avg_noise = np.mean(filtered_fft)
        else:
            avg_noise = 0

        # trouver le pic avec la plus grande amplitude grâce au tri par sélection insertion
        # on définit de base une amplitude max à 0
        max_amp = 0    
        
        for i, amp in enumerate(filtered_fft):
            if amp > max_amp and amp > 3 * avg_noise: # on regarder si l'amplitude est supérieur à 3 fois le bruit moyen pour la comptabiliser
                self.fundamental_freqs[mode].append(filtered_freqs[i])

        # pour avoir une valeur représentative, on fait la moyenne de 3 fréquences mesurées
        if len(self.fundamental_freqs[mode]) > 3:
            self.fundamental_freq[mode] = np.mean(self.fundamental_freqs[mode])
            note = self.freq_to_note(self.fundamental_freq[mode])
            label = self.fundamental_label[mode]

            # on met à jour le label avec la fréquence fondamentale détéctée
            label.setText(f"Fréquence fondamentale détéctée: \n {self.fundamental_freq[mode]:.2f} Hz ({note})")
            self.fundamental_freqs[mode] = []
            
        return freqs, fft_data

    def update_acquisition(self):
        if not self.pause_state:
            # https://people.csail.mit.edu/hubert/pyaudio/docs/#pyaudio.PyAudio.Stream.read
            # self.chunk représente le nombre d'échantillons à capturer
            data = self.stream.read(self.chunk)
            data_table = self.process_audio_data(data) # tableau numpy
            self.curve_acquisition.setData(data_table) # mise à jour des valeurs du plot

    def update_analyse(self):
        if not self.pause_state:
            # https://people.csail.mit.edu/hubert/pyaudio/docs/#pyaudio.PyAudio.Stream.read
            # self.chunk représente le nombre d'échantillons à capturer
            data = self.stream.read(self.chunk)
            data_table = self.process_audio_data(data) # tableau numpy
            freqs, fft_data = self.analyse_fft(data_table, 'live') # fft
            self.curve_analyse.setData(x=freqs, y=fft_data) # mise à jour des valeurs du plot

    def process_file(self, file_path):
        try:
            with wave.open(file_path, 'rb') as wf: # ouvrir le fichier audio en lecture seule (rb = read binary)
                num_frames = wf.getnframes() # return le nombre de frames (échantillons) dans le fichier audio
                sampwidth = wf.getsampwidth() # return le nombre d'octets par échantillons
                num_channels = wf.getnchannels() # return le nombre de channels (1 = mono, 2 = stéréo)
                
                frames = wf.readframes(num_frames)
                # connaître le nombre d'octets par échantillon
                if sampwidth == 1: # si il y a un octet par échantillon
                    format = f"{num_frames * num_channels}B"  # 8-bit
                elif sampwidth == 2: # si il y a deux...
                    format = f"{num_frames * num_channels}h"  # 16-bit audio
                elif sampwidth == 3:
                    format = f"{num_frames * num_channels}i"  # 24-bit audio
                elif sampwidth == 4:
                    format = f"{num_frames * num_channels}i"  # 32-bit audio
                else:
                    print(f"Nombre d'échantillons non supportée: {sampwidth} octets.")
                    
                # https://docs.python.org/3/library/struct.html#struct.unpack
                unpacked_data = struct.unpack(format, frames)
                if sampwidth == 1:
                    data = np.array(unpacked_data, dtype=np.int8)
                elif sampwidth == 2:
                    data = np.array(unpacked_data, dtype=np.int16)
                elif sampwidth == 3 or 4:
                    data = np.array(unpacked_data, dtype=np.int32)

                # garder uniquement un canal (flux mono)
                if num_channels == 2:
                    data = data[::2]  # on prend un échantillon sur deux

                freqs, fft_data = self.analyse_fft(data, 'file')
                self.file_curve.setData(x=freqs, y=fft_data)
        except wave.Error as e:
            self.show_error_message(f"Erreur lors de l'ouverture du fichier: {e}")
        except Exception as e:
            self.show_error_message(f"Erreur lors du traitement du fichier: {e}")
    
    def open_file_dialog(self):
        # https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QFileDialog.html
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilter("Audio Files (*.wav)")
        if file_dialog.exec():
            self.process_file(file_dialog.selectedFiles()[0])

    def pause(self):
        self.pause_state = not self.pause_state
        self.pause_btn.setText("Démarrer ▶️" if self.pause_state else "Pause ⏸️")
        if self.pause_state:
            self.timer.stop()
        else:
            self.timer.start()

    def generate_sound(self, mode):
            if self.fundamental_freq[mode] != None:
                duration = 1  # en secondes
                sample_rate = 44100  # échantillons par seconde

                t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
                audio_data = 0.5 * np.sin(2 * np.pi * self.fundamental_freq[mode] * t)

                stream = self.audio.open(format=pyaudio.paFloat32,
                            channels=1,
                            rate=sample_rate,
                            output=True)

                stream.write(audio_data.astype(np.float32).tobytes())
                stream.stop_stream()
                stream.close()
            else:
                self.show_error_message('Aucune fréquence fondamentale détéctée.')

    def update_min_freq(self, value):
        if value <= self.max_freq:
            self.min_freq = value
            self.min_freq_line.setValue(value)
        else:
            self.show_error_message('La fréquence minimale doit être inférieure à la fréquence maximale.')
            self.min_freq_slider.setValue(self.max_freq-100)
            self.min_freq = self.max_freq-100

    def update_max_freq(self, value):
        if value >= self.min_freq:
            self.max_freq = value
            self.max_freq_line.setValue(value)
        else:
            self.show_error_message('La fréquence maximale doit être supérieure à la fréquence minimale.')
            self.max_freq_slider.setValue(self.min_freq+100)
            self.max_freq = self.min_freq+100

    def show_error_message(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setInformativeText(message)
        msg.setWindowTitle("Erreur")
        msg.exec()

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    widget = AudioStream()
    widget.resize(1300, 700)
    widget.setWindowTitle('Analyse audio en temps réel')
    widget.show()
    sys.exit(app.exec())