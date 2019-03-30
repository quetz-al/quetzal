======
Design
======

This document explains the design, structure and other implementation details
followed in Quetzal.

Concepts
--------

File
^^^^

In Quetzal, the basic unit of data is the file; a collection of bytes stored
at a particular location represented by a filename or a URL.

The specific location where a file is stored is handled by Quetzal and it
depends on what storage backend was configured for the application.

Metadata
^^^^^^^^

Family
^^^^^^

Base family
"""""""""""

Other families
""""""""""""""

Family versioning
^^^^^^^^^^^^^^^^^

Workspace
^^^^^^^^^

Workspace views
"""""""""""""""

Query
^^^^^
