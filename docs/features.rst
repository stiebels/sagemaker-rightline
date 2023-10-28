Features
========

.. toctree::
 :maxdepth: 2

To get an overview of the structure of the project, have a look at the class diagram, which is auto-generated at build time together with the corresponding PUML file:
.. raw:: html
    :file: sagemaker_rightline.svg

⚙️ Configuration
----------------

The ``Configuration`` class is responsible for running the
``Validations`` against the ``Pipeline`` object and returning a
``Report``. The ``Configuration`` class is instantiated with a -
``sagemaker.workflow.pipeline.Pipeline`` object, and - a list of
``Validations``.

✔️ Validations
--------------

A ``Validation`` is a class that inherits from the ``Validation`` base
class. It is responsible for validating a single property of the
``Pipeline`` object. We differentiate between ``Validations`` that check
the ``Pipeline`` object itself (class names beginning with “Pipeline”)
and ``Validations`` that check the ``Pipeline`` object’s ``Step``
objects (class name starting with “Step”). Depending on the specific
``Validation``, a different set of ``StepTypEnums`` may be supported.

For example, the ``StepImagesExist`` supports ``Processing`` and
``Training`` steps. It’s a validation checks that all ImageURI that
Steps of the named types of the ``Pipeline`` object reference indeed
exist on the target ECR.

The following ``Validations`` are currently implemented:

*  ``PipelineParametersAsExpected``
*  ``StepImagesExist``
*  ``StepKmsKeyIdAsExpected``
*  ``StepNetworkConfigAsExpected``
*  ``StepLambdaFunctionExists``
*  ``StepRoleNameExists``
*  ``StepRoleNameAsExpected``
*  ``StepTagsAsExpected``
*  ``StepInputsAsExpected``
*  ``StepOutputsAsExpected``
*  ``StepOutputsMatchInputsAsExpected``
*  ``StepCallbackSqsQueueExists``

In most cases, a ``Validation`` subclass requires passing a ``Rule``
object to its constructor.

📜 Rules
--------

A ``Rule`` is a class that inherits from the ``Rule`` base class. It is
responsible for defining the rule that a ``Validation`` checks for. For
example, passing the list of expected KMSKeyIDs and the ``Rule``
``Equals`` to ``StepKmsKeyIdAsExpected`` will check that all ``Step``
objects of the ``Pipeline`` object have a ``KmsKeyId`` property that
matches the passed KMSKeyIDs.

Note that not all ``Validations`` require a ``Rule`` object,
e.g. ``StepImagesExist``.

The following ``Rules`` are currently implemented:

*  ``Equals``
*  ``Contains``

All rules support the ``negative`` parameter (default: ``False``), which
allows for inverting the rule.

📝 Report
---------

A ``Report`` is a class whose instance is returned by the
``Configuration`` class (optionally a pandas.DataFrame instead). It
contains the results of the ``Validations`` that were run against the
``Pipeline`` object as well as additional information to allow for
further analysis.
