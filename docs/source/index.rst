.. Quetzal documentation master file, created by
   sphinx-quickstart on Sun Mar 17 13:25:21 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Quetzal documentation
=====================

.. Abstract is written in the README.rst so it can be read from github

.. include:: ../../README.rst
   :start-after: abstract_start
   :end-before: abstract_end

The rest of this documentation is divided in three main sections, a
:ref:`general_toc` explanation of Quetzal concepts, design decisions and how
it works. For Quetzal users, that is, those who want to consume the API to
explore or download from the public datasets, the :ref:`user_toc` section shows
the most common use cases and examples. For developers or users that want to
have their own Quetzal server, the :ref:`devel_toc` includes all the
details on creating a development environment, and procedures on how to deploy
a server.

.. toctree::
   :maxdepth: 2
   :caption: General
   :name: general_toc

   intro
   design
   license

.. toctree::
   :maxdepth: 2
   :caption: User documentation
   :name: user_toc

   quickstart
   use_cases

.. toctree::
   :maxdepth: 2
   :caption: Developer documentation
   :name: devel_toc

   dev_quickstart
   structure
   dev_use_cases
   testing
   deployment


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
