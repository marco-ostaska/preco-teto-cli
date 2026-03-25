import re
import typer

app = typer.Typer()

_CNPJ_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")


def _validate_cnpj(cnpj: str) -> None:
    if not _CNPJ_RE.match(cnpj):
        typer.echo(f"CNPJ inválido: {cnpj!r}. Formato esperado: XX.XXX.XXX/XXXX-XX")
        raise typer.Exit(code=1)


@app.command()
def main(cnpj: str) -> None:
    """Avalia fundo de investimento brasileiro por CNPJ."""
    _validate_cnpj(cnpj)
    typer.echo(f"fundos-br: {cnpj} (not yet implemented)")


if __name__ == "__main__":
    app()
