# Third-party dependency notices

The root GNU Affero General Public License, version 3 only (`AGPL-3.0-only`),
applies to relgraph's original code and documentation.
The license texts in this directory concern dependencies, which retain their
own licenses and are not relicensed by the root license.

The current application build uses GMP 6.3.0 and MPFR 4.2.2. Their source archives
come from the GNU distribution server:

- https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz
  SHA-256 `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898`
- https://ftp.gnu.org/gnu/mpfr/mpfr-4.2.2.tar.xz
  SHA-256 `b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01`

`LGPL-3.0.txt` and `GPL-3.0.txt` retain the unmodified dependency notice texts
already carried by the application's selected LGPL v3 notice set. GMP also offers
alternative licensing; this is not a statement that LGPL v3 is its only option.
Dependency distributions retain their own copyright and license notices.

This repository does not bundle GMP/MPFR source or binaries. Downstream desktop
and iOS application wheels currently link them statically. Before distributing
such binaries, resolve the applicable corresponding-source, relinking and other
distribution materials for the chosen model. These notice files alone are not a
claim that those obligations have been fulfilled. Research references are linked,
not relicensed or reproduced as source assets.
