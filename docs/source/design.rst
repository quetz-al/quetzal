======
Design
======

This document explains the design, structure and other implementation details
followed in Quetzal.

Concepts
--------

File
^^^^

In Quetzal, **the basic unit of data is the file**. A file (sometimes referred
as *data file*) is not a Quetzal-specific term; it is exactly what a regular file
is: a collection of bytes stored at a particular location.
The specific location where a file is stored is handled by Quetzal and it
depends on what storage backend was configured for the application.

When Quetzal stores a file, which is uploaded by a user through the
`file upload endpoint <https://api.quetz.al/redoc#operation/workspace_file.create>`_,
it saves it in a storage bucket with a unique URL, while keeping track of
a minimal set of metadata such as its URL, size, checksum, original path and
filename (see the `Base family`_ for more details).

Metadata
^^^^^^^^

Metadata are **key-value pairs associated to each file uploaded to Quetzal**.
They are is intended to represent all that extra information not directly
represented in the *contents* of file. This includes all that useful
information that a researcher may need to provide context or annotations to the
data. For example, the subject identifier, recording hardware used, software
version number of the acquisition software, etc.
Additionally, any information that may be useful to query and filter the data
is also a good candidate to be saved as metadata.
For example, sampling frequency, whether the file contains an error or not,
and even references to other files.

To illustrate what metadata is, let us imagine that you have a dataset of
three files, with the following associated information:

+--------------------------------------------------+---------+---------+------------+-----------+
| filename                                         | subject | session | date       | type      |
+==================================================+=========+=========+============+===========+
| ``study_foo/subject_1/session_1/eeg/signals.xdf``| S001    | 1       | 02/03/2019 | EEG       |
+--------------------------------------------------+---------+---------+------------+-----------+
| ``study_foo/subject_1/session_2/eeg/signals.xdf``| S001    | 2       | 03/03/2019 | EEG       |
+--------------------------------------------------+---------+---------+------------+-----------+
| ``study_foo/subject_2/ecg/cardiac.edf``          | S002    |         | 23/01/2019 | Holter    |
+--------------------------------------------------+---------+---------+------------+-----------+

In this case, the first file has four metadata entries: the subject identifier,
its session number, the date and a categorical value indicating that the data
file contains EEG signals. We can even say that the filename is a metadata
as well, because it has a key (*filename*) and a value (*study/subject_x/...*).

The other files have similar metadata, but note that the third file does not
have a session number. This is one of the reasons Quetzal works with
*unstructured* metadata; you are not obligated to follow the same metadata
structure for all files.


Family
^^^^^^

Once you start thinking about metadata, and how it is just a key-value pair
associated to a file, you can think of a myriad of metadata to associate to
your files. How do you organize these key-value pairs? *Families* provide a
semantic organization of your metadata.

In Quetzal, a family is a **set of metadata keys**, defined for some common
semantic or organizational purpose.

In the table presented above, it would make sense to keep the subject, session
and date metadata grouped together, since this information is related to the
study protocol. The data type, on the other hand, could be organized elsewhere,
just for the purpose of this example, in a family that groups all
signal-related information. Moreover, the filename can be related to a *base*
family, which is information that Quetzal needs for bookkeeping.

Here is an updated table proposal with the metadata and their families:

+--------------------------------------------------+--------------+---------+------------+------------------+
| *base* family                                    | *study* family                      | *signals* family |
+--------------------------------------------------+--------------+---------+------------+------------------+
| filename                                         | subject      | session | date       | type             |
+==================================================+==============+=========+============+==================+
| ``study_foo/subject_1/session_1/eeg/signals.xdf``| S001         | 1       | 02/03/2019 | EEG              |
+--------------------------------------------------+--------------+---------+------------+------------------+
| ``study_foo/subject_1/session_2/eeg/signals.xdf``| S001         | 2       | 03/03/2019 | EEG              |
+--------------------------------------------------+--------------+---------+------------+------------------+
| ``study_foo/subject_2/ecg/cardiac.edf``          | S002         |         | 23/01/2019 | Holter           |
+--------------------------------------------------+--------------+---------+------------+------------------+


Base family
"""""""""""

Each file has a **minimal set of metadata** needed by the Quetzal application
for keeping track of files, where they are stored, etc. These metadata are
defined under the *base* family. Its keys are defined in the
:py:class:`quetzal.app.models.BaseMetadataKeys` enumeration, which are:

* **id**: A unique identifier of the file. This is generated by Quetzal when
  the file is created as a UUID4_ number. For example:
  ``f5b460ad-b1e9-4e09-ac43-2c670ffeac6d``
* **url**: A uniform resource locator that indicates where Quetzal stores this
  file. Usually (*but not necessarily!*), it has its **id** in it. For example:
  ``gs://some_bucket/f5b460ad-b1e9-4e09-ac43-2c670ffeac6d``. Note that the URL
  does not include the filename: these are just metadata like any other and
  many files in Quetzal could have the exact same filename!
* **filename**: The *basename* of the file when it was uploaded. Note that
  it is *only* the basename, that is, there is no path in it. For example:
  ``signals.xdf``.
* **path**: The *pathname* of the file when it was uploaded.
* **size**:
* **checksum**:
* **date**:
* **state**:


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


.. _UUID4: https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)
