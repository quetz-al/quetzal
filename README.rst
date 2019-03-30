.. class:: center

    .. image:: docs/source/_static/logo_h.png
       :height: 100px
       :alt: Quetzal logo

    Quetzal — A RESTful API for data and metadata management.

.. badges will go here


Quetzal
=======

.. abstract_start

Quetzal (short for Quetzalcóatl: the feathered snake) is a RESTful API designed
to store data files and manage their associated metadata.
Its main target audience are reserchers and data scientists looking for a
unique bank of file datasets, without having to manage and download
them directly.

There are two scenarios where Quetzal was designed to help:

* Imagine you want to apply a data processing pipeline to a large dataset.
  There are several solutions on how to execute and parallelize your code, but
  *where is the data?* Moreover, imagine that you want to do a transverse study:
  How do you manage the different sources? How to download them?

  Quetzal provides a single data source with a simple API that will let you
  define easily the scope of your study and, with a short code that
  uses `Quetzal client <https://github.com/quetz-al/quetzal-client>`_, you will
  be able to download your dataset.

* Let's say that you are preparing a new study implying some data collection
  protocol. You could define a procedure where the data operators or technicians
  take care to copy the data files in a disk, Google Drive or Dropbox, along
  with the notes associated with each session, like subject study identifier,
  date, age, temperature, etc. Doing this manually would be error-prone.
  Moreover, the structure of these notes (i.e. the metadata) may evolve quickly,
  so you either save them as manual notes, text files, or some database that
  gives you the flexibility to quickly adapt its structre.

  Using the Quetzal API and a short Python code, you automate the upload and
  safe storage of the study files, associate the metadata of these files while
  having the liberty to set and modify the metadata structure as you see fit.


In brief, Quetzal offers the following main features:

* **Storage** of data files, based on cloud storage providers, which benefits
  from all of the features from the provider, such as virtually infinite
  storage size.
* **Unstructured metadata** associated to each file*. Quetzal does not force
  the user to organize your metadata in a particular way, it lets the user keep
  whatever structure they prefer.
* **Structured metadata views** for metadata exploration or dataset definition.
  By leveraging Postgres SQL, unstructured metadata can be queried as JSON
  objects, letting the user express what subset of the data they want to use.
* **Metadata versioning**. Changes on metadata are versioned, which is
  particularly useful to ensure that a dataset are reproducible.
* Endpoints and operations defined using the
  `OpenAPI v3 specification <https://github.com/OAI/OpenAPI-Specification>`_.

.. abstract_end

Documentation
-------------

Quetzal's documentation is available on
`readthedocs <https://quetzal-api.readthedocs.org>`_. The API documentation is
embedded into its specification; the best way to visualize it is through the
is also a
`ReDoc API reference documentation site <https://stage.quetz.al/redoc>`_.



Contribute
----------

- Issue Tracker: https://github.com/quetz-al/quetzal/issues
- Source Code: https://github.com/quetz-al/quetzal

Support
-------

If you are having issues, please let us know by opening an issue or by sending
an email to support@quetz.al.

License
-------

The project is under the BSD 3-clause license.

See the `authors <./AUTHORS.rst>`_ page for more information on the authors and
copyright holders.
