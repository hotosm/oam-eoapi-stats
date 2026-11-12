# oam-eoapi-stats

Lightweight statistics service for the OpenAerialMap eoAPI catalog: scene counts, deduplicated coverage and an aggregated footprint, served as a small read-only API.

> [!WARNING]
> This project is in early development. The API is not stable yet.

## Installation

```bash
uv add oam-eoapi-stats
```

## Development

```bash
uv sync
uv run pytest
uv run pre-commit install
```

## License

[MIT](LICENSE)
