<h1 align="center">
  <br>
  Analyse Audio
  <br>
</h1>

<h4 align="center">Permet d'analyser, en temps réél, les sons grâce à la FFT.</h4>

## Avancement

* 11/12/24: Mise en place du but, de comment y arriver (avec quel bibliothèques/frameworks). Création d'une fenêtre de base avec https://doc.qt.io/qtforpython-6/gettingstarted.html#getting-started (random hello)

* 17/12/24: Obtention d'un graphique en temps réel avec l'amplitude par rapport au temps. Ajout d'un bouton pause/démarrer pour fixer le graph et l'analyser.

* 18/12/24: Création des tabs 'Acquisition' et 'Analyse'. Obtention du graphique avec la transformée de Fourier (tab analyse). A faire: bouton pause pour le tab analyse

* 22/12/24: Bouton pause fonctionnel pour les deux tabs. Création de la fonction analyse_fft pour en déduire une fréquence fondamentale (marche 2/3 du temps mais capte malgré tout des fréquences issues du bruit).

* 23/12/24: Widget pour montrer la fréquence fondamentale et indication sur la note jouée. Ajout d'un tab paramètre pour modifier notamment les paramètres d'analyses de la FFT. Message d'erreur si la fréquence min est supérieur à la fréquence max et inversement.

* 24/12/24: Ajout d'un tab pour lire et faire la fft sur un fichier disponible localement. Clean le code et création de fonctions qui sont utilisées pour plusieurs tab (ex: une fonction fft pour le tab analyse et fichier).

* 25/12/24: Met l'acquisition et l'analyse de données en temps réel en pause lorsque l'utilisateur n'est pas sur un des deux tabs, afin d'utiliser le moins de ressources possibles. Bouton permettant de générer la fréquence fondamentale du son entendu (pour vérifier s'il correspond). Enlever le seuil minimum de bruit comme il est calculé dynamiquement dans analyse_fft. Changer les couleurs des fréquences min et max.

* 27/12/24: Créé un bouton supplémentaire dans le tab 'fichier', pour jouer le son initial du fichier et le comparer plus aisément avec la fréquence entendue.

## Mes autres projets...

- [Shapy](https://github.com/damienRifflart/Shapy) - An iOs sport application.
- [Marks](https://github.com/damienRifflart/StudyStats) - Automatically get the number of hours, and classes for the next 100 days.

## Contact

> Gmail: [rifflartdamiencontact@gmail.com](rifflartdamiencontact@gmail.com) &nbsp;&middot;&nbsp;
> GitHub: [@damienRifflart](https://github.com/damienRifflart) &nbsp;&middot;&nbsp;