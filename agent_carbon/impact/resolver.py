class ModelResolver:
    """Filet de sécurité : mappe un modèle non encore enregistré upstream
    vers un modèle connu d'EcoLogits, via une table d'alias explicite.
    Table vide au départ (le registre 0.11.0 couvre déjà les modèles actuels)."""

    def __init__(self, aliases: dict[str, str]):
        self.aliases = aliases

    def resolve(self, model: str) -> tuple[str, bool]:
        if model in self.aliases:
            return self.aliases[model], True
        return model, False
