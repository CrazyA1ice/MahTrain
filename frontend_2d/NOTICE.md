# Upstream attribution and ownership

This module **uses actual** [@kobalab/majiang-ui](https://github.com/kobalab/majiang-ui) v1.6.1, MIT, by Satoshi Kobayashi.
The entire eight original Stylus table style files (names preserved) are vendored unmodified from [kobalab/Majiang](https://github.com/kobalab/Majiang), MIT, by Satoshi Kobayashi, to compile their known desktop/table layout.
The 28 sprite GIF images in `assets/img/` are byte-for-byte copied from that repository `dist/img` and are kept at their original image dimensions and encoding. The adapted web page uses the **real UI.Shoupai, UI.He, UI.pai and UI.mianzi** implementations, not a visually imitated table.
Original MIT copyright and license texts are retained in `LICENSE-MAJIANG.txt` and `LICENSE-MAJIANG-UI.txt`.

This adapter uses MahTrain's Python rules and private seat-zero API as the sole rule authority; it does not adopt Japanese riichi/chi scoring, nor surface opponents' hidden tiles.
