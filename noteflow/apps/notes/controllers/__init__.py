"""Note endpoint controllers."""

from .index import Notes
from .new import NewNote
from .detail import NoteDetail
from .edit import EditNote
from .delete import DeleteNote

__all__ = ["Notes", "NewNote", "NoteDetail", "EditNote", "DeleteNote"]
