"""The shape of the feedback. The AI is forced to answer in exactly this format."""
from pydantic import BaseModel, Field


class VocabItem(BaseModel):
    word: str = Field(description="A useful word or phrase that came up in the lesson.")
    definition: str = Field(description="A short, simple definition the student will understand.")
    in_context: str = Field(description="The sentence from the lesson where it was used.")


class Correction(BaseModel):
    original: str = Field(description="What the student actually said, containing the error.")
    corrected: str = Field(description="The corrected version.")
    explanation: str = Field(description="One or two simple sentences explaining why.")


class GrammarPoint(BaseModel):
    name: str = Field(description="Name of the grammar point only, e.g. 'Present Perfect'.")
    form: str = Field(description="How it is formed, e.g. 'have/has + past participle'.")
    usage: str = Field(description="When we use it, with an example from the lesson if possible.")


class StudentFeedback(BaseModel):
    lesson_summary: str = Field(description="2-3 sentences summarising what the lesson covered.")
    positive_feedback: list[str] = Field(description="2-3 specific things the student did well.")
    grammar_points: list[GrammarPoint] = Field(description="Grammar taught or practised. Can be empty.")
    vocab_items: list[VocabItem] = Field(description="Vocabulary that came up. Can be empty.")
    corrections: list[Correction] = Field(description="The student's real errors. Can be empty.")
    improvement_areas: list[str] = Field(description="1-2 'Next time, try...' suggestions.")
    practice_task: str = Field(description="One small task to do before the next lesson.")
