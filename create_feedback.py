"""Turns a StudentFeedback object into a tidy Word document."""
from datetime import date

from docx import Document
from docx.shared import Pt


def _table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, headers):
        cell.text = text
        cell.paragraphs[0].runs[0].font.bold = True
    for row in rows:
        for cell, text in zip(table.add_row().cells, row):
            cell.text = text
    doc.add_paragraph()  # breathing room after the table


def _bullets(doc, items):
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def create_feedback_doc(feedback, output_path, lesson_date=None):
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)

    doc.add_heading("Lesson Feedback", level=0)
    doc.add_paragraph((lesson_date or date.today()).strftime("%A %d %B %Y"))

    doc.add_heading("What we covered", level=1)
    doc.add_paragraph(feedback.lesson_summary)

    if feedback.positive_feedback:
        doc.add_heading("What you did well", level=1)
        _bullets(doc, feedback.positive_feedback)

    if feedback.grammar_points:
        doc.add_heading("Grammar", level=1)
        _table(doc, ["Grammar point", "Form", "Usage"],
               [(g.name, g.form, g.usage) for g in feedback.grammar_points])

    if feedback.vocab_items:
        doc.add_heading("Vocabulary", level=1)
        _table(doc, ["Word", "Meaning", "From the lesson"],
               [(v.word, v.definition, v.in_context) for v in feedback.vocab_items])

    if feedback.corrections:
        doc.add_heading("Corrections", level=1)
        _table(doc, ["What you said", "Better", "Why"],
               [(c.original, c.corrected, c.explanation) for c in feedback.corrections])

    if feedback.improvement_areas:
        doc.add_heading("What to work on", level=1)
        _bullets(doc, feedback.improvement_areas)

    doc.add_heading("Practice before our next lesson", level=1)
    doc.add_paragraph(feedback.practice_task)

    doc.save(str(output_path))
