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
        # parametres
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

        layout = QtWidgets.QVBoxLayout(self) # créé un layout vertical
        layout.addWidget(self.tab_widget)
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

        # button pause
        self.pause_state = False
        self.pause_btn = QtWidgets.QPushButton("Pause ⏸️")
        self.pause_btn.clicked.connect(self.pause)
        self.pause_btn.setFixedWidth(100)

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_acquisition)
        self.timer.start(30) # toutes les 30ms

        layout.addWidget(self.pause_btn)
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

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer_analyse = QtCore.QTimer()
        self.timer_analyse.timeout.connect(self.update_analyse)
        self.timer_analyse.start(30) # toutes les 30ms

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
        fft_data = np.abs(np.fft.rfft(data_table))
        
        # calcul des fréquences correspondantes
        # shttps://numpy.org/doc/2.1/reference/generated/numpy.fft.rfftfreq.html
        # rfftfreq génère un tableau contenant les fréquences correspondantes aux données FFT.
        freqs = np.fft.rfftfreq(len(data_table), d=1/self.rate)
        
        # Mettre à jour le graphique d'analyse
        self.curve_analyse.setData(x=freqs, y=fft_data)

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