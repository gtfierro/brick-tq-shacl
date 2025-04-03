import subprocess
from pytqshacl.run import infer as pytqshacl_infer, validate as pytqshacl_validate
import platform
import tempfile
import rdflib
from rdflib import OWL, SH
from rdflib.term import BNode, URIRef, _SKOLEM_DEFAULT_AUTHORITY, rdflib_skolem_genid
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

# monkeypatch BNode.skolemize with a new function
def _new_bnode_skolemize(
    self, authority: Optional[str] = None, basepath: Optional[str] = None
) -> URIRef:
    """Create a URIRef "skolem" representation of the BNode, in accordance
    with http://www.w3.org/TR/rdf11-concepts/#section-skolemization

    .. versionadded:: 4.0
    """
    if authority is None:
        authority = _SKOLEM_DEFAULT_AUTHORITY
    if basepath is None:
        basepath = rdflib_skolem_genid
    skolem = "%s%s" % (basepath, str(self).replace(" ", "_"))
    return URIRef(urljoin(authority, skolem))


BNode.skolemize = _new_bnode_skolemize


def infer(
        data_graph: rdflib.Graph, ontologies: rdflib.Graph
        ):
    # remove imports
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    data_graph = data_graph.skolemize()
    # remove imports from ontologies too
    ontologies.remove((None, OWL.imports, None))

    # create a temporary directory and save the data_graph and ontologies to data.ttl and ontologies.ttl respectively
    with tempfile.TemporaryDirectory() as temp_dir:
        data_graph_path = Path(temp_dir) / "data.ttl"
        (data_graph + ontologies).serialize(data_graph_path, format="turtle")
        ontologies_path = Path(temp_dir) / "ontologies.ttl"
        (data_graph + ontologies).serialize(ontologies_path, format="turtle")

        # run the pytqshacl_infer function
        inferred_graph = pytqshacl_infer(data_graph_path, shapes=ontologies_path)

        # parse stdout into a graph
        inferred_triples = rdflib.Graph()
        inferred_triples.parse(data=inferred_graph.stdout, format="turtle")
        inferred_triples = inferred_triples + data_graph
        # add imports back
        for imp in imports:
            inferred_triples.add(imp)
        return inferred_triples.de_skolemize()


def validate(data_graph: rdflib.Graph, shape_graphs: rdflib.Graph):

    # infer the data graph
    data_graph = infer(data_graph, shape_graphs)

    # Remove imports
    data_graph.remove((None, OWL.imports, None))

    # Skolemize the data graph
    data_graph_skolemized = data_graph.skolemize()

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Define the target path within the temporary directory
        data_graph_path = temp_dir_path / "data.ttl"
        shape_graphs_path = temp_dir_path / "shapes.ttl"

        # Serialize the graphs to files
        (data_graph_skolemized + shape_graphs).serialize(data_graph_path, format="turtle")
        shape_graphs.serialize(shape_graphs_path, format="turtle")

        # Run the pytqshacl_validate function
        validation_result = pytqshacl_validate(data_graph_path, shapes=shape_graphs_path)

        # Parse the validation result into a graph
        report_g = rdflib.Graph()
        report_g.parse(data=validation_result.stdout, format="turtle")

        # Check if there are any sh:resultSeverity sh:Violation predicate/object pairs
        has_violation = len(
            list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
        )
        conforms = len(
            list(report_g.subjects(predicate=SH.conforms, object=rdflib.Literal(True)))
        )
        validates = not has_violation or conforms

        return validates, report_g, str(report_g.serialize(format="turtle"))
