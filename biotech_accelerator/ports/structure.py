"""Data models for protein structures."""


class StructureNotFoundError(Exception):
    """Raised when a structure cannot be found."""

    def __init__(self, pdb_id: str):
        self.pdb_id = pdb_id
        super().__init__(f"Structure not found: {pdb_id}")
