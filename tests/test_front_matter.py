from prarup.frontmatter import latex_to_plain
from prarup.models import Author

def test_latex_to_plain():
    assert latex_to_plain(r"\textbf{\emph{Abstract}---A 12\% gain \& more}") == "Abstract—A 12% gain & more"
    assert latex_to_plain(r"Rao\textsuperscript{1}") == "Rao"


def test_latex_to_plain_reads_pandocs_escapes_for_caret_and_tilde():
    assert latex_to_plain(r"(x\^{}2) and 5\textasciitilde{}10 and a~b") == "(x^2) and 5~10 and a b"


def test_label_line_name_affiliation_with_commas_and_email():
    from prarup.frontmatter import title_and_authors

    title, authors = title_and_authors([
        '"YOLO-Based Object Detection and Player Tracking for Automated Football Match Analysis"',
        "Author(s):", "Dipto Roy",
        "Department of Computer Science and Engineering, Parul University, Gujarat, India",
        "Email: 2303051050235@paruluniversity.ac.in",
    ])
    assert title.startswith("YOLO-Based Object Detection")
    assert authors == [Author("Dipto Roy", "Department of Computer Science and Engineering, "
                              "Parul University, Gujarat, India, Email: 2303051050235@paruluniversity.ac.in")]


def test_superscript_markers_tie_authors_to_numbered_affiliations():
    from prarup.frontmatter import read_authors

    authors = read_authors([
        "Kayeleigh Sharp¹, Brooklyn Christofis², Hossein Eslamiat³",
        "¹ Northern Arizona University, kayeleigh.sharp@nau.edu",
        "² San Diego State University",
        "³ Ohio University",
    ])
    assert [(a.name, a.affiliation) for a in authors] == [
        ("Kayeleigh Sharp", "Northern Arizona University, kayeleigh.sharp@nau.edu"),
        ("Brooklyn Christofis", "San Diego State University"),
        ("Hossein Eslamiat", "Ohio University"),
    ]


def test_one_name_then_affiliation_lines():
    from prarup.frontmatter import read_authors

    authors = read_authors(["Renas Rajab Asaad",
                            "Department of Computer Science, College of Science, Nawroz University, Kurdistan-Region, Iraq",
                            "Renas.Rekany@Nawroz.edu.krd"])
    assert len(authors) == 1
    assert authors[0].name == "Renas Rajab Asaad"
    assert authors[0].affiliation.startswith("Department of Computer Science")
    assert authors[0].affiliation.endswith("Renas.Rekany@Nawroz.edu.krd")


def test_ieee_block_several_names_share_one_affiliation():
    from prarup.frontmatter import read_authors

    authors = read_authors(["Sana Hafeez, Lina Mohjazi, Muhammad Ali Imran and Yao Sun\n"
                            "James Watt School of Engineering, University of Glasgow"])
    assert [a.name for a in authors] == ["Sana Hafeez", "Lina Mohjazi", "Muhammad Ali Imran", "Yao Sun"]
    assert all(a.affiliation == "James Watt School of Engineering, University of Glasgow" for a in authors)
