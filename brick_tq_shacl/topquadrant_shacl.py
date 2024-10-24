import subprocess
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

        # set the SHACL_HOME environment variable to point to the shacl-1.4.2 directory
        # so that the shaclinfer.sh script can find the shacl.jar file
        env = {"SHACL_HOME": str(Path(__file__).parent / "topquadrant_shacl")}
        # get the shacl-1.4.2/bin/shaclinfer.sh script from brickschema.bin in this package
        # using pkgutil. If using *nix, use .sh; else if on windows use .bat
        if platform.system() == "Windows":
            script = [
                str(Path(__file__).parent / "topquadrant_shacl/bin/shaclinfer.bat")
            ]
        else:
            script = [
                "/bin/sh",
                str(Path(__file__).parent / "topquadrant_shacl/bin/shaclinfer.sh"),
            ]

        # Initialize the size of the graph
        previous_size = 0
        current_size = len(data_graph_skolemized)
        current_iter = 0

        # Run the shaclinfer multiple times until the skolemized data graph stops changing in size
        while previous_size != current_size and current_iter < _MAX_EXTERNAL_LOOPS:
            (data_graph_skolemized + ontologies).serialize(
                target_file_path, format="turtle"
            )
            try:
                logging.debug(f"Running {script} -datafile {target_file_path}")
                proc = subprocess.run(
                    [
                        *script,
                        "-datafile",
                        target_file_path,
                        "-maxiterations",
                        str(max_iterations),
                    ],
                    capture_output=True,
                    universal_newlines=True,
                    check=False,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                raise Exception(f"Error running shaclinfer: {e.output}")
            # Write logs to a file in the temporary directory (or the desired location)
            inferred_file_path = temp_dir_path / "inferred.ttl"
            with open(inferred_file_path, "w") as f:
                for line in proc.stdout.splitlines():
                    if "::" not in line:
                        f.write(f"{line}\n")
            try:
                inferred_triples = rdflib.Graph()
                inferred_triples.parse(inferred_file_path, format="turtle")
                logging.debug(f"Got {len(inferred_triples)} inferred triples")
            except Exception as e:
                raise Exception(f"Error parsing inferred triples: {e}\nMaybe due to SHACL inference process exception?\n{proc.stderr}")
            for s, p, o in inferred_triples:
                if isinstance(s, BNode) or isinstance(o, BNode):
                    continue
                data_graph_skolemized.add((s, p, o))

            # Update the size of the graph
            previous_size = current_size
            current_size = len(data_graph_skolemized)
            current_iter += 1

        expanded_graph = data_graph_skolemized
        # add imports back in
        for imp in imports:
            expanded_graph.add(imp)
        return expanded_graph


def validate(data_graph: rdflib.Graph, shape_graphs: rdflib.Graph):
    # remove imports
    data_graph.remove((None, OWL.imports, None))

    # set the SHACL_HOME environment variable to point to the shacl-1.4.2 directory
    # so that the shaclinfer.sh script can find the shacl.jar file
    env = {"SHACL_HOME": str(Path(__file__).parent / "topquadrant_shacl")}
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Define the target path within the temporary directory
        target_file_path = temp_dir_path / "data.ttl"

        inferred_graph = infer(data_graph, shape_graphs)

        # combine the inferred graph with the shape graphs
        (inferred_graph + shape_graphs).serialize(target_file_path, format="ttl")

        # get the shacl-1.4.2/bin/shaclvalidate.sh script from the same directory
        # as this file
        if platform.system() == "Windows":
            script = [
                str(Path(__file__).parent / "topquadrant_shacl/bin/shaclvalidate.bat")
            ]
        else:
            script = [
                "/bin/sh",
                str(Path(__file__).parent / "topquadrant_shacl/bin/shaclvalidate.sh"),
            ]
        try:
            logging.debug(f"Running {script} -datafile {target_file_path}")
            proc = subprocess.run(
                [
                    *script,
                    "-datafile",
                    target_file_path,
                    "-maxiterations",
                    "100",
                ],
                capture_output=True,
                universal_newlines=True,
                check=False,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error running shaclinfer: {e.output}")

        # Write logs to a file in the temporary directory (or the desired location)
        report_file_path = temp_dir_path / "report.ttl"
        with open(report_file_path, "w") as f:
            for line in proc.stdout.splitlines():
                if "::" not in line:  # filter out log output
                    f.write(f"{line}\n")
        try:
            report_g = rdflib.Graph()
            report_g.parse(report_file_path, format="turtle")
        except Exception as e:
            raise Exception(f"Error parsing report: {e}\nMaybe due to SHACL validation process exception?\n{proc.stderr}")

        # check if there are any sh:resultSeverity sh:Violation predicate/object pairs
        has_violation = len(
            list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
        )
        conforms = len(
            list(report_g.subjects(predicate=SH.conforms, object=rdflib.Literal(True)))
        )
        validates = not has_violation or conforms

        return validates, report_g, str(report_g.serialize(format="turtle"))
