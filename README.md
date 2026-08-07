# pse — Python Search Engine

_Find Python packages across PyPI, Conda channels, and other compatible indexes._

pse is a cross-source command-line Python package search tool. It searches Python
packages without installing packages or using a package manager at runtime.

## Features

- Search PyPI and conda-forge from one command.
- Add extra PyPI Simple indexes and Conda channels.
- Produce human-readable tables or structured JSON.

## Usage

### Using `pse` on-the-fly

You can run `pse` directly with `uvx`, `pipx` or `pixi exec` for a quick search without installing anything.

```powershell
uvx pse "pkg"
```

</details>

<details>
<summary>pipx</summary>

```powershell
pipx run pse "pkg"
```

</details>

<details>
<summary>pixi exec</summary>

```powershell
pixi exec pse "pkg"
```

</details>

### Installing `pse` for repeated use

You can install `pse` as global command with `uv tool install` for repeated use:

```powershell
uv tool install pse
pse "pkg"
```

## Use-cases

Search for a package on PyPI and Conda:

```powershell
pse "pkg"
```

Search an additional PyPI index:

```powershell
pse "pkg" --pypi-index https://download.pytorch.org/whl/cu126
```

Search an additional Conda channel:

```powershell
pse "pkg" --conda-channel bioconda
```

Use multiple extra sources:

```powershell
pse "pkg" --pypi-index https://download.pytorch.org/whl/cu126 --conda-channel bioconda
```

## Sources

### PyPI

pse searches the [PyPI Simple API](https://pypi.org/simple/). Additional
PyPI indexes must expose a compatible Simple index, such as the PyTorch wheel
index.

### Conda

pse searches current_repodata.json.bz2 for the selected Conda channel and
platform. It also searches noarch unless the requested platform is already
noarch.

Channel names are resolved through conda.anaconda.org. Full channel URLs are
also accepted.

The reduced current_repodata metadata is fast, but it may not contain every
historical Conda package version.

## JSON output

`pse` can produce structured JSON output for programmatic consumption and agent friendly use. The JSON output contains a `results` array with one entry per source. Each entry contains the source name, package name, and an array of available versions.:

```json
{
  "query": "torch",
  "platform": "win-64",
  "results": [
    {
      "source": "pypi",
      "name": "torch",
      "versions": [
        {
          "version": "2.13.0",
          "build": null,
          "platform": null
        }
      ]
    }
  ]
}
```

If a source fails, an errors array is added to the document.
