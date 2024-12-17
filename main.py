import struct
import sys
import numpy as np
from PySide6 import QtCore, QtWidgets
import pyaudio
import pyqtgraph as pg


class AudioStream(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()        

        # https://people.csail.mit.edu/hubert/pyaudio/docs/#pyaudio.PyAudio.open
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

        # https://pyqtgraph.readthedocs.io/en/latest/getting_started/plotting.html
        # graphique
        self.plot = pg.PlotWidget() # composant de PyQtGraph: permet d'afficher des graphiques 2D
        self.plot.setYRange(-4000, 4000) # comme c'est codé 16 bits: 2^16 / 2 = 32 768. Les valeurs vont de -32 768 au min à 32 767 au max
        self.curve = self.plot.plot(pen='cyan') # on plot une ligne ou courbe qui représentera les valeurs
        
        # button pause
        self.pause_state = False
        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause)

        self.layout = QtWidgets.QGridLayout(self) # créé un layout
        self.layout.addWidget(self.plot)
        self.layout.addWidget(self.pause_btn)

        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html
        # timer: toutes les x secondes, on recapture les échantillons
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30) # toutes les 30ms

    # prises des échantillons
    def update_plot(self):
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
        self.curve.setData(data_table)

    # bouton pause/démarrer
    def pause(self):
        self.pause_state = not self.pause_state

        if self.pause_state:
            self.timer.stop()
            self.pause_btn.setText("Démarrer")

        else:
            self.pause_btn.setText("Pause")
            self.timer.start()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = AudioStream()
    widget.resize(1200, 700)
    widget.setWindowTitle('Analyse audio en temps réel')
    widget.show()

    sys.exit(app.exec())