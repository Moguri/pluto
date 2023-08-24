# Project Pluto

This project is an sandbox/playground for expirementing with various techniques and ideas in the Panda3D game engine.
In general, this goal is a networked, multi-player, arcade shooter.

This will require sorting out:
* Level building and loading
* Multi-player networking

The following libraries will be used, battle-tested, and improved on:
* simplepbr
* pman
* blend2bam
* panda3d-gltf

The project is split into two python packages:
* src/lib - generic code that aims to be easy to re-use in other projects (and maybe get split into their own libraries)
* src/game - code specific to the game itself

## Preparing the environment

* Install and setup [git lfs](https://git-lfs.com/)
* Setup a [virtual environment](https://docs.python.org/3/tutorial/venv.html) (optional, but recommended)
* Install [Blender](https://www.blender.org/download/) (should be made available on the system `PATH`)
* Install the project in develop mode: `pip install -e .[test]`
* Run the game using `pman run`
* To build game assets without running use `pman build` (this is done automatically as part of `run`)

## Running tests
Install test dependencies with:

```bash
python -m pip install -e .[test]
```

Run tests with pytest:

```bash
python -m pytest
```

## Building binaries

To build binaries run:
```bash
pman dist
```

## License

* Anything mentioned in [CREDITS.md](CREDITS.md) have licenses as specified in the file
* Any remaining code is [BSD 3-Clause](https://choosealicense.com/licenses/bsd-3-clause/)
