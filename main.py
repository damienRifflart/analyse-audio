from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel, QMessageBox
import pyaudio, math, sys, numpy as np, struct, pyqtgraph as pg

class AudioStream(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()        

        # tabs
        self.tab_widget = QTabWidget()
        self.acquisitionTab = QWidget()
        self.analyseTab = QWidget()
        self.parametreTab = QWidget()

        self.tab_widget.addTab(self.acquisitionTab, "Acquisition")
        self.tab_widget.addTab(self.analyseTab, "Analyse")
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
            # on spécifie les différents paramètres dit en haut
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
        self.fundamental_freqs = []
        self.fundamental_freq = None
        self.noise_threshold = 30000
        self.min_freq = 250
        self.max_freq = 1100

        self.initTabAcquisition()
        self.initTabAnalyse()
        self.initTabParametres()

    # https://stackoverflow.com/questions/64505024/turning-frequencies-into-notes-in-python
    def freq_to_note(self, freq):
        notes = ['La', 'La#', 'Si', 'Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#']

        note_number = 12 * math.log2(freq / 440) + 49  
        note_number = round(note_number)
            
        note = (note_number - 1 ) % len(notes)
        note = notes[note]
        
        octave = (note_number + 8 ) // len(notes)
        
        return f"{note}{octave}"

    def initTabAcquisition(self):
        layout = QVBoxLayout(self.acquisitionTab)

        # https://pyqtgraph.readthedocs.io/en/latest/getting_started/plotting.html
        # graphique
        plot = pg.PlotWidget() # composant de PyQtGraph: permet d'afficher des graphiques 2D
        plot.setYRange(-4000, 4000) # comme c'est codé 16 bits: 2^16 / 2 = 32 768. Les valeurs vont de -32 768 au min à 32 767 au max
        plot.setLabel("bottom", "Temps (s)")
        plot.setLabel("left", "Amplitude (UA)")
        self.curve_acquisition = plot.plot(pen='cyan') # on plot une ligne ou courbe qui représentera les valeurs

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_acquisition)
        self.timer.start(30) # toutes les 30ms

        layout.addWidget(plot)

    def initTabAnalyse(self):
        # layout horizontal
        layout = QtWidgets.QHBoxLayout(self.analyseTab)

        # https://pyqtgraph.readthedocs.io/en/latest/getting_started/plotting.html
        # graphique
        plot = pg.PlotWidget() # composant de PyQtGraph: permet d'afficher des graphiques 2D
        plot.setYRange(-4000, 4000) # comme c'est codé 16 bits: 2^16 / 2 = 32 768. Les valeurs vont de -32 768 au min à 32 767 au max
        plot.setLabel("bottom", "Fréquences (Hz)")
        plot.setLabel("left", "Amplitude (UA)")
        self.curve_analyse = plot.plot(pen='cyan') # on plot une ligne ou courbe qui représentera les valeurs

        # ligne pour le seuil de bruit
        self.noise_threshold_line = pg.InfiniteLine(self.noise_threshold, angle=0, pen=pg.mkPen('r', width=2))
        plot.addItem(self.noise_threshold_line)

        # ligne pour la fréquence minimale
        self.min_freq_line = pg.InfiniteLine(self.min_freq, angle=90, pen=pg.mkPen('g', width=2))
        plot.addItem(self.min_freq_line)

        # ligne pour la fréquence maximale
        self.max_freq_line = pg.InfiniteLine(self.max_freq, angle=90, pen=pg.mkPen('g', width=2))
        plot.addItem(self.max_freq_line)

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer.timeout.connect(self.update_analyse)


        # panel de droite pour afficher les fréquences détéctées
        # https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QVBoxLayout.html
        self.freq_panel = QWidget()  # créé un widget pour montrer les fréquences

        freq_layout = QVBoxLayout(self.freq_panel)  # créé un layout vertical pour le widget
        self.fundamental_label = QLabel(f"Fréquence fondamentale détéctée: \n {self.fundamental_freq}")
        self.fundamental_label.setAlignment(QtCore.Qt.AlignCenter)
        self.fundamental_label.setStyleSheet("font-size: 30px;")
        freq_layout.addWidget(self.fundamental_label)  # ajoute le label au layout
        
        layout.addWidget(plot, stretch=2) # prend 2/3 du tab
        layout.addWidget(self.freq_panel, stretch=1) # prend 1/3 du tab

    def initTabParametres(self):
        layout = QVBoxLayout(self.parametreTab)

        # slider pour le seuil de bruit
        self.noise_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.noise_slider.setMinimum(0)
        self.noise_slider.setMaximum(40000)
        self.noise_slider.setValue(self.noise_threshold)
        self.noise_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.noise_slider.setTickInterval(2500)
        self.noise_slider.valueChanged.connect(self.update_noise_threshold)

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

        layout.addWidget(QLabel("Seuil de bruit"))
        layout.addWidget(self.noise_slider)
        layout.addWidget(QLabel("Fréquence minimale"))
        layout.addWidget(self.min_freq_slider)
        layout.addWidget(QLabel("Fréquence maximale"))
        layout.addWidget(self.max_freq_slider)

    def update_acquisition(self):
        # https://people.csail.mit.edu/hubert/pyaudio/docs/#pyaudio.PyAudio.Stream.read
        # self.chunk représente le nombre d'échantillons à capturer
        data = self.stream.read(self.chunk)

        # Conversion des données en un tableau lisible par Numpy
        # data est une séquence d'octets au format binaire, que Numpy ne peut pas directement traiter.
        # struct.unpack convertit ces octets en valeurs numériques (ex. : 7, -8, 11)

        # https://docs.python.org/3/library/struct.html#struct.unpack
        # on récupère le nombre d'octets: 1024 échantillons codés sur 16 bits (2 octets), donc 1024 * 2 = 2048 octets
        # on rajoute B pour byte ou octet en français, ça permet de préciser à la fonction unpack que ce sont 2048 octets
        num_octets = f"{2 * self.chunk}B"
        unpacked_data = struct.unpack(num_octets, data) # décode les octets de data en valeurs numériques

        # une fois qu'on a des valeurs numériques, il faut les convertir en un tableau Numpy (de type 16 bits)
        data_table = np.array(unpacked_data, dtype=np.int16)
        data_table = data_table[::2] # slice le tableau pour prendre qu'un élement sur deux (=> flux mono). Syntaxe: sequence[start:end:step]
        
        # mettre à jour les données du graph
        self.curve_acquisition.setData(data_table)

    def update_analyse(self):
        data = self.stream.read(self.chunk)
        
        # converti data en un tableau de valeurs numériques
        num_octets = f"{2 * self.chunk}B"
        unpacked_data = struct.unpack(num_octets, data)
        data_table = np.array(unpacked_data, dtype=np.int16)
        data_table = data_table[::2]  # flux mono
        
        # transformée de Fourier (FFT)
        # https://numpy.org/doc/2.1/reference/generated/numpy.fft.rfft.html
        # on utilise rfft car data contient des nombres réels (pas complexes).
        self.fft_data = np.abs(np.fft.rfft(data_table))
        
        # calcul des fréquences correspondantes
        # shttps://numpy.org/doc/2.1/reference/generated/numpy.fft.rfftfreq.html
        # rfftfreq génère un tableau contenant les fréquences correspondantes aux données FFT.
        self.freqs = np.fft.rfftfreq(len(data_table), d=1/self.rate)
        
        # fonction pour avoir la fréquence fondamentale
        self.analyse_fft()

        # mettre à jour le graphique d'analyse
        self.curve_analyse.setData(x=self.freqs, y=self.fft_data)

    def analyse_fft(self):
        # masque pour filtrer les fréquences trop hautes/basses
        freq_mask = (self.freqs >= self.min_freq) & (self.freqs <= self.max_freq)
        
        # filtrer les données FFT et les fréquences correspondantes
        filtered_fft = self.fft_data[freq_mask]
        filtered_freqs = self.freqs[freq_mask]
        
        # calcul du bruit moyen
        if len(filtered_fft) > 0:
            avg_noise = np.mean(filtered_fft)
        else:
            avg_noise = 0
        
        # trouver le pic avec la plus grande amplitude grâce au tri par sélection insertion
        max_amp = 0 # on définit de base une amplitude max à 0

        for i, amp in enumerate(filtered_fft):
            if amp > max_amp:
                max_amp = amp

                # on regarder si l'amplitude est supérieur à 3 fois le bruit moyen pour la comptabiliser
                if amp > 3 * avg_noise:
                    max_freq = filtered_freqs[i]
                    self.fundamental_freqs.append(max_freq)

        # pour avoir une valeur représentative, on fait la moyenne de 3 fréquences mesurées
        if len(self.fundamental_freqs) > 3:
            self.fundamental_freq = np.mean(self.fundamental_freqs)
            note = self.freq_to_note(self.fundamental_freq)
            self.fundamental_label.setText(f"Fréquence fondamentale détéctée: \n {self.fundamental_freq:.2f} Hz ({note})") # update le texte du label
            self.fundamental_freqs = []

    def pause(self):
        self.pause_state = not self.pause_state

        if self.pause_state:
            self.timer.stop()
            self.pause_btn.setText("Démarrer ▶️")

        else:
            self.pause_btn.setText("Pause ⏸️")
            self.timer.start()
        
    def update_noise_threshold(self, value):
        self.noise_threshold = value
        self.noise_threshold_line.setValue(value)

    def update_min_freq(self, value):
        if value <= self.max_freq:
            self.min_freq = value
            self.min_freq_line.setValue(value)
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setInformativeText('La fréquence minimale doit être inférieure à la fréquence maximale.')
            msg.setWindowTitle("Erreur")
            msg.exec()

            self.min_freq_slider.setValue(self.max_freq-100)
            self.min_freq = self.max_freq-100

    def update_max_freq(self, value):
        if value >= self.min_freq:
            self.max_freq = value
            self.max_freq_line.setValue(value)
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setInformativeText('La fréquence maximale doit être supérieure à la fréquence minimale.')
            msg.setWindowTitle("Erreur")
            msg.exec()

            self.max_freq_slider.setValue(self.min_freq+100)
            self.max_freq = self.min_freq+100

if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = AudioStream()
    widget.resize(1300, 700)
    widget.setWindowTitle('Analyse audio en temps réel')
    widget.show()

    sys.exit(app.exec())