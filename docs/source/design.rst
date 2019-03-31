======
Design
======

This document explains the concepts and design decisions followed in Quetzal.

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

Once you start considering metadata, and how it is just a key-value pair
associated to a file, you may think of a myriad of metadata to associate to
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

Here is an updated table with the metadata and their families:

+--------------------------------------------------+--------------+---------+------------+-----------------+
| *base* family                                    | *study* family                      | *signal* family |
+--------------------------------------------------+--------------+---------+------------+-----------------+
| filename                                         | subject      | session | date       | type            |
+==================================================+==============+=========+============+=================+
| ``study_foo/subject_1/session_1/eeg/signals.xdf``| S001         | 1       | 02/03/2019 | EEG             |
+--------------------------------------------------+--------------+---------+------------+-----------------+
| ``study_foo/subject_1/session_2/eeg/signals.xdf``| S001         | 2       | 03/03/2019 | EEG             |
+--------------------------------------------------+--------------+---------+------------+-----------------+
| ``study_foo/subject_2/ecg/cardiac.edf``          | S002         |         | 23/01/2019 | Holter          |
+--------------------------------------------------+--------------+---------+------------+-----------------+

A row on this table, corresponding to the metadata of one file, can be
represented as a JSON object as shown below. This representation is how the
Quetzal API responds to a request for the metadata of a file.

.. code-block:: json

  {
    "base": {
       "filename": "study_foo/subject_1/session_1/eeg/signals.xdf"
    },
    "study": {
       "subject": "S001",
       "session": 1,
       "date": "2019-03-02"
    },
    "signal": {
       "type": "EEG"
    }
  }


Base family
"""""""""""

Each file has a **minimal set of metadata** needed by the Quetzal application
for keeping track of files, where they are stored, etc. These metadata are
defined under the *base* family. Its keys are defined in the
:py:class:`quetzal.app.models.BaseMetadataKeys` enumeration, which are:

* **id**: A unique identifier of the file. This is generated by Quetzal when
  the file is created as a UUID4_ number. For example:
  ``f5b460ad-b1e9-4e09-ac43-2c670ffeac6d``.
* **url**: A uniform resource locator that indicates where Quetzal stores this
  file. Usually (*but not necessarily!*), it has its **id** in it. For example:
  ``gs://some_bucket/f5b460ad-b1e9-4e09-ac43-2c670ffeac6d``. Note that the URL
  does not include the filename: these are just metadata like any other and
  many files in Quetzal could have the exact same filename!
* **filename**: The *basename* of the file when it was uploaded. Note that
  it is *only* the basename, that is, there is no path in it. For example:
  ``signals.xdf``.
* **path**: The *pathname* of the file when it was uploaded.
* **size**: Size in bytes of the file contents.
* **checksum**: MD5 digest of the files contents.
* **date**: Datetime when the file was uploaded.
* **state**: Enumeration indicating the state of the file. Used to mark
  temporary or deleted files.

The base family is entirely managed by Quetzal. It can only have the keys listed
above. Their values are set by Quetzal when the file is uploaded. It is not
possible to change them afterwards, with the sole exception of the path.

Other families
""""""""""""""

Quetzal lets the user define any number of families. Within each family, there
can be any number of keys. There is only one constraint: the **id** key is
reserved and managed by Quetzal.


Unstructured metadata
^^^^^^^^^^^^^^^^^^^^^

The contents of metadata in Quetzal are not constrained to a particular schema.
They can be a string, a number, date, and even lists or nested objects. This
features gives great flexibility on how and what to store as metadata.

Considering all the elements mentioned in the `Base family`_,
`Other families`_ and this section, we can expand completely define and
expand the metadata of the first file in this page as:

.. code-block:: json

  {
    "base": {
       "id": "f5b460ad-b1e9-4e09-ac43-2c670ffeac6d",
       "url": "gs://some_bucket/f5b460ad-b1e9-4e09-ac43-2c670ffeac6d",
       "filename": "signals.xdf",
       "path": "study_foo/subject_1/session_1/eeg",
       "size": 19058370,
       "checksum": "9529f1439ec59ca105de75973a241574",
       "date": "2019-03-02T09:37:05.618034+00:00",
       "state": "READY"
    },
    "study": {
       "id": "f5b460ad-b1e9-4e09-ac43-2c670ffeac6d",
       "subject": "S001",
       "session": 1,
       "date": "2019-03-02"
    },
    "signal": {
       "id": "f5b460ad-b1e9-4e09-ac43-2c670ffeac6d",
       "type": "EEG",
       "sampling_rate": 512,
       "samples": 15360,
       "channels": ["Fpz", "F3", "F4", "Fz"],
       "device": {
          "name": "foo",
          "manufacturer": "bar",
          "firwmare_version": "1.0.1"
       }
    }
  }

Note that:

* All families have an **id** key with the same value.
* The base family has been populated with all the required keys.
* The signal family has been augmented with more complex objects types.


Family versioning
^^^^^^^^^^^^^^^^^

Metadata hold important information that is frequently used in many data
analyses. For instance, questions like
*"Is there a significant difference of X feature for each subject?"* is a
question that needs to use the subject identifier, which is stored as metadata.
Due to their importance, it is desirable to have some change or version control
mechanism for the metadata.

Quetzal tracks the changes of metadata with family versioning. Each family has
a version number. Quetzal guarantees that requests for the metadata of a
particular family version are always the same. Changes of metadata values
result in a new version number for its associated family.


Workspace
^^^^^^^^^

Global vs local metadata
""""""""""""""""""""""""

Workspace views
"""""""""""""""



Query
^^^^^

API
---

Usage workflow
--------------



.. _UUID4: https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)
