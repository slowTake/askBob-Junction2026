import ezdxf

from app.ingest.dxf_shapes import shapes


def test_text_keeps_its_cad_anchor_alignment_for_registration() -> None:
    doc = ezdxf.new()
    doc.modelspace().add_text(
        "1.01",
        dxfattribs={
            "insert": (2, 3),
            "height": 0.18,
            "halign": 1,
            "valign": 2,
        },
    )
    (item,) = list(shapes(doc.modelspace(), 1000))
    assert item.points == [(2000, 3000)]
    assert (item.text_halign, item.text_valign) == (1, 2)


def test_mtext_top_right_and_middle_centre_anchors() -> None:
    doc = ezdxf.new()
    doc.modelspace().add_mtext("1.01", dxfattribs={"attachment_point": 3})
    doc.modelspace().add_mtext("1.02", dxfattribs={"attachment_point": 5})
    a, b = list(shapes(doc.modelspace(), 1))
    assert (a.text_halign, a.text_valign) == (2, 3)
    assert (b.text_halign, b.text_valign) == (1, 2)
