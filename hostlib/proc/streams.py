"""Reading a process's output while it runs.

One thread per pipe reads raw bytes as they become available, decodes them
incrementally so a multi-byte character split across two reads is still one
character, keeps the text, and hands each chunk to a callback. Both pipes are
drained concurrently, so a process that fills one can never block on the other,
and the last line is kept whether or not it ended in a newline.

Key components:
    - StreamReader: the thread
    - READ_SIZE: bytes requested per read

Dependencies:
    - standard library only
"""

from __future__ import annotations

import codecs
import threading
from collections.abc import Callable
from typing import IO

READ_SIZE: int = 65536


class StreamReader(threading.Thread):
    """Drain one binary pipe to text, live.

    Attributes:
        stream: the pipe, in binary mode and unbuffered.
        write: receives each decoded chunk as it arrives.
        parts: the chunks, in order.

    Example:
        >>> import io
        >>> reader = StreamReader(io.BytesIO("h\\u00e9\\n".encode()), "utf-8", lambda text: None)
        >>> reader.start(); reader.join(); reader.text
        'hé\\n'
    """

    def __init__(self, stream: IO[bytes], encoding: str, write: Callable[[str], None]) -> None:
        super().__init__(daemon=True)
        self.stream: IO[bytes] = stream
        self.write: Callable[[str], None] = write
        self.decoder: codecs.IncrementalDecoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        self.parts: list[str] = []

    def run(self) -> None:
        """Read until end of stream, decoding and forwarding each chunk."""
        try:
            while True:
                data: bytes | None = self.stream.read(READ_SIZE)
                if not data:
                    break
                self.chunk_handle(self.decoder.decode(data))
            self.chunk_handle(self.decoder.decode(b"", final=True))
        finally:
            self.stream.close()

    def chunk_handle(self, text: str) -> None:
        """Keep a decoded chunk and forward it."""
        if not text:
            return
        self.parts.append(text)
        self.write(text)

    @property
    def text(self) -> str:
        """Everything read so far."""
        return "".join(self.parts)
