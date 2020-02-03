## Installation

``` bash
snap install --beta --devmode dotrun
```

OR

``` bash
multipass launch -n dotrun bionic
multipass exec dotrun -- sudo snap install --beta --devmode dotrun
multipass mount $HOME dotrun
alias dotrun='multipass exec dotrun -- /snap/bin/dotrun -C `pwd`'
```

## Conversion

- Remove `run`, `.docker-project`, `.pip*`, `.yarn*`
- Add `.dotrun.json` and `.venv` to `.gitignore`
- Swap `0.0.0.0` with `$(hostname -I)` in `package.json`
