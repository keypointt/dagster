from collections import namedtuple
from typing import Optional, Set

from dagster import check
from dagster.core.definitions.events import AssetKey
from dagster.core.types.dagster_type import resolve_dagster_type
from dagster.utils.backcompat import experimental_arg_warning

from .utils import DEFAULT_OUTPUT, check_valid_name


class OutputDefinition:
    """Defines an output from a solid's compute function.

    Solids can have multiple outputs, in which case outputs cannot be anonymous.

    Many solids have only one output, in which case the user can provide a single output definition
    that will be given the default name, "result".

    Output definitions may be typed using the Dagster type system.

    Args:
        dagster_type (Optional[Any]): The type of this output. Users should provide one of the
            :ref:`built-in types <builtin>`, a dagster type explicitly constructed with
            :py:func:`as_dagster_type`, :py:func:`@usable_as_dagster_type <dagster_type`, or
            :py:func:`PythonObjectDagsterType`, or a Python type. Defaults to :py:class:`Any`.
        name (Optional[str]): Name of the output. (default: "result")
        description (Optional[str]): Human-readable description of the output.
        is_required (Optional[bool]): Whether the presence of this field is required. (default: True)
        io_manager_key (Optional[str]): The resource key of the output manager used for this output.
            (default: "io_manager").
        metadata (Optional[Dict[str, Any]]): (Experimental) A dict of the metadata for the output.
            For example, users can provide a file path if the data object will be stored in a
            filesystem, or provide information of a database table when it is going to load the data
            into the table.
        asset_key (Optional[Union[AssetKey, OutputContext -> AssetKey]]): (Experimental) An AssetKey
            (or function that produces an AssetKey from the OutputContext) which should be associated
            with this OutputDefinition. Used for tracking lineage information through Dagster.
        asset_partitions (Optional[Union[Set[str], OutputContext -> Set[str]]]): (Experimental) A
            set of partitions of the given asset_key (or a function that produces this list of
            partitions from the OutputContext) which should be associated with this OutputDefinition.
    """

    def __init__(
        self,
        dagster_type=None,
        name=None,
        description=None,
        is_required=None,
        io_manager_key=None,
        metadata=None,
        asset_key=None,
        asset_partitions=None,
    ):
        self._name = check_valid_name(check.opt_str_param(name, "name", DEFAULT_OUTPUT))
        self._dagster_type = resolve_dagster_type(dagster_type)
        self._description = check.opt_str_param(description, "description")
        self._is_required = check.opt_bool_param(is_required, "is_required", default=True)
        self._manager_key = check.opt_str_param(
            io_manager_key, "io_manager_key", default="io_manager"
        )
        if metadata:
            experimental_arg_warning("metadata", "OutputDefinition.__init__")
        self._metadata = metadata

        if asset_key:
            experimental_arg_warning("asset_key", "OutputDefinition.__init__")

        self._is_asset = asset_key is not None

        if callable(asset_key):
            self._asset_key_fn = asset_key
        else:
            asset_key = check.opt_inst_param(asset_key, "asset_key", AssetKey)
            self._asset_key_fn = lambda _: asset_key

        if asset_partitions:
            experimental_arg_warning("asset_partitions", "OutputDefinition.__init__")
            check.param_invariant(
                asset_key is not None,
                "asset_partitions",
                'Cannot specify "asset_partitions" argument without also specifying "asset_key"',
            )
        if callable(asset_partitions):
            self._asset_partitions_fn = asset_partitions
        else:
            asset_partitions = check.opt_set_param(asset_partitions, "asset_partitions", str)
            self._asset_partitions_fn = lambda _: asset_partitions

    @property
    def name(self):
        return self._name

    @property
    def dagster_type(self):
        return self._dagster_type

    @property
    def description(self):
        return self._description

    @property
    def optional(self):
        return not self._is_required

    @property
    def is_required(self):
        return self._is_required

    @property
    def io_manager_key(self):
        return self._manager_key

    @property
    def metadata(self):
        return self._metadata

    @property
    def is_dynamic(self):
        return False

    @property
    def is_asset(self):
        return self._is_asset

    def get_asset_key(self, context) -> Optional[AssetKey]:
        """Get the AssetKey associated with this OutputDefinition for the given
        :py:class:`OutputContext` (if any).

        Args:
            context (OutputContext): The OutputContext that this OutputDefinition is being evaluated
            in
        """
        return self._asset_key_fn(context)

    def get_asset_partitions(self, context) -> Optional[Set[str]]:
        """Get the set of partitions associated with this OutputDefinition for the given
        :py:class:`OutputContext` (if any).

        Args:
            context (OutputContext): The OutputContext that this OutputDefinition is being evaluated
            in
        """
        return self._asset_partitions_fn(context)

    def mapping_from(self, solid_name, output_name=None):
        """Create an output mapping from an output of a child solid.

        In a CompositeSolidDefinition, you can use this helper function to construct
        an :py:class:`OutputMapping` from the output of a child solid.

        Args:
            solid_name (str): The name of the child solid from which to map this output.
            input_name (str): The name of the child solid's output from which to map this output.

        Examples:

            .. code-block:: python

                output_mapping = OutputDefinition(Int).mapping_from('child_solid')
        """
        return OutputMapping(self, OutputPointer(solid_name, output_name))


class DynamicOutputDefinition(OutputDefinition):
    """
    (EXPERIMENTAL) Variant of :py:class:`OutputDefinition` for an output that will dynamically
    alter the graph at runtime. Each copy of :py:class:`DynamicOutput` corresponding to this
    definition that is yielded from the solid will create a copy of the downstream graph.

        .. code-block:: python

            @solid(
                config_schema={
                    "path": Field(str, default_value=file_relative_path(__file__, "sample"))
                },
                output_defs=[DynamicOutputDefinition(str)],
            )
            def files_in_directory(context):
                path = context.solid_config["path"]
                dirname, _, filenames = next(os.walk(path))
                for file in filenames:
                    yield DynamicOutput(os.path.join(dirname, file), mapping_key=_clean(file))
    """

    @property
    def is_dynamic(self):
        return True


class OutputPointer(namedtuple("_OutputPointer", "solid_name output_name")):
    def __new__(cls, solid_name, output_name=None):
        return super(OutputPointer, cls).__new__(
            cls,
            check.str_param(solid_name, "solid_name"),
            check.opt_str_param(output_name, "output_name", DEFAULT_OUTPUT),
        )


class OutputMapping(namedtuple("_OutputMapping", "definition maps_from")):
    """Defines an output mapping for a composite solid.

    Args:
        definition (OutputDefinition): Defines the output of the composite solid.
        solid_name (str): The name of the child solid from which to map the output.
        output_name (str): The name of the child solid's output from which to map the output.
    """

    def __new__(cls, definition, maps_from):
        return super(OutputMapping, cls).__new__(
            cls,
            check.inst_param(definition, "definition", OutputDefinition),
            check.inst_param(maps_from, "maps_from", OutputPointer),
        )
