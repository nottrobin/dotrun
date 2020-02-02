## Installation

### Ubuntu

``` bash
snap install --beta --devmode dotrun
```

### MacOS

First install [multipass](https://multipass.run/), then run:

``` bash
# Create multipass instance called "dotrun"
multipass launch -n dotrun bionic

# Install dotrun snap
multipass exec dotrun -- sudo snap install --beta --devmode dotrun

# Share your home directory with the dotrun multipass VM
multipass mount $HOME dotrun

# Set up alias in your shell's RC file
rcfile=~/.$(basename `echo $SHELL`)rc
echo "alias dotrun='multipass exec dotrun -- /snap/bin/dotrun -C `pwd`'" >> ${rcfile}
source ${rcfile}
```

## Conversion

- Remove `run`, `.docker-project`, `.pip*`, `.yarn*`
- Add `.dotrun.json` and `.venv` to `.gitignore`
- Swap `0.0.0.0` with `$(hostname -I)` in `package.json`
