import struct
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel
import pyqtgraph as pg
import pyaudio
import sys

class AudioStream(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()        

        # tabs
        self.tab_widget = QTabWidget()
        self.acquisitionTab = QWidget()
        self.analyseTab = QWidget()

        self.tab_widget.addTab(self.acquisitionTab, "Acquisition")
        self.tab_widget.addTab(self.analyseTab, "Analyse")

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
        self.noise_threshold = 30000
        self.min_freq = 400
        self.max_freq = 1000

        self.initTabAcquisition()
        self.initTabAnalyse()

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
        layout = QVBoxLayout(self.analyseTab)

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

        layout.addWidget(plot)

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
        
        # fonction pour avori la fréquence fondamentale
        fundamental = self.analyse_fft()
        if fundamental is not None: # si il y en a une
            print(f"Fréquence fondamentale: {fundamental:.1f}Hz") # tronque à 1 chiffre après la virgule

        # mettre à jour le graphique d'analyse
        self.curve_analyse.setData(x=self.freqs, y=self.fft_data)

    def analyse_fft(self):
        # masque pour filtrer les fréquences trop hautes/basses
        freq_mask = (self.freqs >= self.min_freq) & (self.freqs <= self.max_freq)
        
        # filtrer les données FFT et les fréquences correspondantes
        filtered_fft = self.fft_data[freq_mask]
        filtered_freqs = self.freqs[freq_mask]
        
        # calcul du bruit moyen
        avg_noise = np.mean(filtered_fft)
        
        # trouver le pic avec la plus grande amplitude grâce au tri par sélection insertion
        max_amp = 0 # on définit de base une amplitude max à 0
        fundamental_freq = None

        for i, amp in enumerate(filtered_fft):
            if amp > max_amp:
                max_amp = amp

                # on regarder si l'amplitude est supérieur à 3 fois le bruit moyen pour la comptabiliser
                if amp > 3 * avg_noise:
                    max_freq = filtered_freqs[i]
                    self.fundamental_freqs.append(max_freq)

        # pour avoir une valeur représentative, on fait la moyenne de 3 fréquences mesurées
        if len(self.fundamental_freqs) > 3:
            fundamental_freq = np.mean(self.fundamental_freqs)
            # et on réinitialise la liste
            self.fundamental_freqs = []

        return fundamental_freq

    def pause(self):
        self.pause_state = not self.pause_state

        if self.pause_state:
            self.timer.stop()
            self.pause_btn.setText("Démarrer ▶️")

        else:
            self.pause_btn.setText("Pause ⏸️")
            self.timer.start()
        
if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = AudioStream()
    widget.resize(1300, 700)
    widget.setWindowTitle('Analyse audio en temps réel')
    widget.show()

    sys.exit(app.exec())