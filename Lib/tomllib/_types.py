# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

from typing import Callable, Tuple

# Type annotations
ParseFloat = Callable[[str], object]
Key = Tuple[str, ...]
Pos = int
