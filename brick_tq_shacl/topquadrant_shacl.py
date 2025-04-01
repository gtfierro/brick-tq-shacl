import tempfile
import rdflib
from pytqshacl.run import infer as pytqshacl_infer, validate as pytqshacl_validate
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
_MAX_EXTERNAL_LOOPS = 10


def infer(
    data_graph: rdflib.Graph, ontologies: rdflib.Graph, max_iterations: int = 100
):
    # remove imports
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    # remove imports from ontologies too
    ontology_imports = ontologies.remove((None, OWL.imports, None))

    # skolemize before inference
    data_graph_skolemized = data_graph

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Define the target path within the temporary directory
        target_file_path = temp_dir_path / "data.ttl"
        (data_graph_skolemized + ontologies).serialize(
            target_file_path, format="turtle"
        )
        # add imports back
        for imp in ontology_imports:
            ontologies.add(imp)

        # Use pytqshacl's infer method
        inferred_graph = pytqshacl_infer(target_file_path, shapes=None)
        inferred_triples = rdflib.Graph()
        inferred_triples.parse(data=inferred_graph, format="turtle")
        logging.debug(f"Got {len(inferred_triples)} inferred triples")
        for s, p, o in inferred_triples:
            if isinstance(s, BNode) or isinstance(o, BNode):
                continue
            data_graph_skolemized.add((s, p, o))

        expanded_graph = data_graph_skolemized
        # add imports back in
        for imp in imports:
            expanded_graph.add(imp)
        return expanded_graph


def validate(data_graph: rdflib.Graph, shape_graphs: rdflib.Graph):
    # remove imports
    data_graph.remove((None, OWL.imports, None))

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Define the target path within the temporary directory
        target_file_path = temp_dir_path / "data.ttl"
    inferred_graph = infer(data_graph, shape_graphs)
    (inferred_graph + shape_graphs).serialize(target_file_path, format="ttl")
    report, report_g, report_str = pytqshacl_validate(target_file_path, shapes=None)
    try:
        report_g = rdflib.Graph()
        report_g.parse(data=report_str, format="turtle")
    except Exception as e:
        raise Exception(f"Error parsing report: {e}")

        # check if there are any sh:resultSeverity sh:Violation predicate/object pairs
        has_violation = len(
            list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
        )
        conforms = len(
            list(report_g.subjects(predicate=SH.conforms, object=rdflib.Literal(True)))
        )
        validates = not has_violation or conforms

        return validates, report_g, str(report_g.serialize(format="turtle"))
