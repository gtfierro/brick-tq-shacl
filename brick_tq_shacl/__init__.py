"""brick-tq-shacl public API.

Provides SHACL-based inference and validation utilities on top of the
TopQuadrant SHACL engine (pytqshacl) for rdflib.Graph objects.

Version: 0.4.0
"""
import sys
from importlib import import_module
from pathlib import Path
import tempfile
from typing import Tuple, Optional
from rdflib import Graph, OWL, SH, Literal
from rdflib.namespace import RDF

try:
    pytqshacl = import_module("pytqshacl")
except ModuleNotFoundError:  # pragma: no cover - runtime dependency check
    vendor_src = Path(__file__).with_name("_vendor") / "pytqshacl" / "src"
    if not vendor_src.is_dir():
        raise
    vendor_src_str = str(vendor_src.resolve())
    if vendor_src_str not in sys.path:
        sys.path.insert(0, vendor_src_str)
    pytqshacl = import_module("pytqshacl")
    sys.modules.setdefault("pytqshacl", pytqshacl)

tqinfer = pytqshacl.infer
tqvalidate = pytqshacl.validate

__version__ = "0.4.0"
__all__ = ["infer", "validate", "pretty_print_report", "__version__"]


def clean_stdout(stdout: str) -> str:
    """
    Cleans stdout by removing lines that get emitted by TopQuadrant.
    """
    lines = stdout.splitlines()
    cleaned_lines = [
            line for line in lines if "::" not in line
    ]
    return "\n".join(cleaned_lines)


def infer(
    data_graph: Graph,
    ontologies: Optional[Graph] = None,
    min_iterations: int = 1,
    max_iterations: int = 10,
    early_isomorphic_exit: bool = False,
) -> Graph:
    """
    Performs SHACL-based inference on a data graph using a set of ontologies.

    This function iteratively applies inference rules from the ontologies to the data
    graph until no new triples are generated. The process is handled by the
    TopQuadrant SHACL engine (`tqinfer`).

    Note: The function removes `owl:imports` statements from the graphs to process
    them as self-contained units. These are restored before returning.

    Args:
        data_graph (Graph): The RDF graph to be expanded with inferences.
        ontologies (Optional[Graph]): A graph containing SHACL shapes and ontology
                                      definitions to guide the inference process. If not
                                      provided, `data_graph` is assumed to contain the
                                      ontologies.
        min_iterations (int): The minimum number of inference iterations.
        max_iterations (int): The maximum number of inference iterations.
        early_isomorphic_exit (bool): Stop iterating once consecutive inferred
            graphs are isomorphic when True.

    Returns:
        Graph: The data graph enriched with inferred triples.
    """
    # remove imports to treat graphs as self-contained
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    data_graph = data_graph.skolemize()
    # remove imports from ontologies too
    if ontologies:
        ontology_imports = list(ontologies.triples((None, OWL.imports, None)))
        ontologies.remove((None, OWL.imports, None))
    else:
        ontologies = Graph()
        ontology_imports = []

    # Use a temporary directory to store intermediate RDF files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # write all ontologies to a new tempfile
        ontologies_file_path = temp_dir_path / "ontologies.ttl"
        ontologies.serialize(ontologies_file_path, format="turtle")

        data_graph_size = len(data_graph)
        data_graph_size_changed = True
        current_iteration = 0
        previous_inferred_graph: Optional[Graph] = None

        # Iteratively apply inference until no new triples are generated
        while (
            data_graph_size_changed or current_iteration < min_iterations
        ) and current_iteration < max_iterations:
            # write data_graph to a tempfile
            target_file_path = temp_dir_path / "data.ttl"
            (data_graph + ontologies).serialize(target_file_path, format="turtle")

            # Run TopQuadrant SHACL inference
            inferred_graph_result = tqinfer(
                target_file_path,
                tool_args=("-maxiterations", "10", "-noImports"),
            )
            inferred_graph_result.stdout = clean_stdout(inferred_graph_result.stdout)
            # read the inferred graph from the stdout of the completed process
            inferred_graph = Graph().parse(
                data=inferred_graph_result.stdout, format="turtle"
            )
            if early_isomorphic_exit and (
                previous_inferred_graph is not None
                and inferred_graph.isomorphic(previous_inferred_graph)
            ):
                break
            previous_inferred_graph = inferred_graph
            data_graph += inferred_graph

            # Check if the graph size has changed to continue or stop iterating
            data_graph_size_changed = len(data_graph) != data_graph_size
            data_graph_size = len(data_graph)
            current_iteration += 1
    # re-add imports that were removed earlier
    for imp in imports:
        data_graph.add(imp)
    if ontologies:
        for imp in ontology_imports:
            ontologies.add(imp)
    return data_graph.de_skolemize()


def pretty_print_report(report_g: Graph) -> str:
    """
    Pretty prints a SHACL validation report graph.

    Args:
        report_g (Graph): The validation report graph.

    Returns:
        str: A formatted string representation of the report.
    """
    report_node = next(report_g.subjects(RDF.type, SH.ValidationReport), None)
    if not report_node:
        return "No validation report found in the graph."

    conforms = bool(report_g.value(report_node, SH.conforms))
    output_lines = [f"Validation Report"]
    output_lines.append(f"Conforms: {conforms}")

    results = list(report_g.objects(report_node, SH.result))

    if not conforms and results:
        output_lines.append(f"\nValidation Results ({len(results)}):")
        for i, result_node in enumerate(results, 1):
            output_lines.append(f"\n--- Result {i} ---")

            severity = report_g.value(result_node, SH.resultSeverity)
            if severity:
                output_lines.append(
                    f"Severity: {report_g.namespace_manager.normalizeUri(severity)}"
                )

            focus_node = report_g.value(result_node, SH.focusNode)
            if focus_node:
                output_lines.append(
                    f"Focus Node: {focus_node.n3(report_g.namespace_manager)}"
                )

            message = report_g.value(result_node, SH.resultMessage)
            if message:
                output_lines.append(f"Message: {message}")

            path = report_g.value(result_node, SH.resultPath)
            if path:
                output_lines.append(f"Path: {path.n3(report_g.namespace_manager)}")

            value = report_g.value(result_node, SH.value)
            if value:
                output_lines.append(f"Value: {value.n3(report_g.namespace_manager)}")

            scc = report_g.value(result_node, SH.sourceConstraintComponent)
            if scc:
                output_lines.append(
                    f"Source Constraint: {report_g.namespace_manager.normalizeUri(scc)}"
                )

            source_shape = report_g.value(result_node, SH.sourceShape)
            if source_shape:
                output_lines.append(
                    f"Source Shape: {source_shape.n3(report_g.namespace_manager)}"
                )

    return "\n".join(output_lines)


def validate(
    data_graph: Graph,
    shape_graphs: Optional[Graph] = None,
    min_iterations: int = 1,
    max_iterations: int = 10,
    early_isomorphic_exit: bool = False,
) -> Tuple[bool, Graph, str]:
    """
    Validates a data graph against a set of SHACL shapes.

    This function first performs inference on the data graph using the shapes
    graph as ontologies, then validates the inferred graph against the shapes.

    Note: The function removes `owl:imports` statements from the graphs to process
    them as self-contained units. These are restored before returning.

    Args:
        data_graph (Graph): The RDF graph to be validated.
        shape_graphs (Optional[Graph]): A graph containing the SHACL shapes. If not
                                        provided, `data_graph` is assumed to contain
                                        the shapes.
        min_iterations (int): The minimum number of inference iterations.
        max_iterations (int): The maximum number of inference iterations.
        early_isomorphic_exit (bool): Stop inference iterations early when
            consecutive inferred graphs are isomorphic if True.

    Returns:
        Tuple[bool, Graph, str]: A tuple containing:
            - A boolean indicating if the graph conforms to the shapes.
            - The validation report graph itself (rdflib.Graph).
            - A human-readable string representation of the validation report.
    """
    # First, perform inference on the data graph using the shape graphs as ontologies.
    # This materializes triples that may be needed for validation.
    data_graph = infer(
        data_graph,
        shape_graphs,
        min_iterations=min_iterations,
        max_iterations=max_iterations,
        early_isomorphic_exit=early_isomorphic_exit,
    )

    # remove imports to treat graphs as self-contained
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    if shape_graphs:
        shape_imports = list(shape_graphs.triples((None, OWL.imports, None)))
        shape_graphs.remove((None, OWL.imports, None))
    else:
        shape_imports = []

    # Use a temporary directory to store intermediate RDF files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        data_graph_path = temp_dir_path / "data.ttl"

        # Serialize the combined data and shape graphs to a file for validation
        graph_to_validate = data_graph
        if shape_graphs:
            graph_to_validate = graph_to_validate + shape_graphs
        graph_to_validate.serialize(data_graph_path, format="turtle")

        # Run the TopQuadrant SHACL validation engine
        validation_result = tqvalidate(
            data_graph_path,
            tool_args=("-maxiterations", "10", "-addBlankNodes", "-noImports"),
        )
        validation_result.stdout = clean_stdout(validation_result.stdout)

    # re-add imports that were removed earlier
    for imp in imports:
        data_graph.add(imp)
    if shape_graphs:
        for imp in shape_imports:
            shape_graphs.add(imp)

    # Parse the validation report into an RDF graph
    report_g = Graph()
    report_g.parse(data=validation_result.stdout, format="turtle")

    # Determine validation success.
    # The graph is valid if it conforms explicitly (sh:conforms true) or
    # there are no violations (sh:resultSeverity sh:Violation).
    has_violation = len(
        list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
    )
    conforms = len(list(report_g.subjects(predicate=SH.conforms, object=Literal(True))))
    validates = not has_violation or conforms

    return validates, report_g, pretty_print_report(report_g)
