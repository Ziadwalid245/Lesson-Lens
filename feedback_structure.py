from pydantic import BaseModel, Field
class VocabItem(BaseModel):
    word:str = Field( description="Hard word or vocabulary term that was brought up in the lesson.")
    definition:str = Field( description="The definition of the vocabulary word.")
    in_context:str = Field( description="The context in which the word was used during the lesson.")    
class Corrections(BaseModel):
    original:str = Field( description="The original sentence or phrase that contained an error.")
    corrected:str = Field( description="The corrected version of the sentence or phrase.")
    explanation:str = Field( description="An explanation of the correction made, including grammar rules or usage tips.")
class GrammarPoint(BaseModel):
    explained_garmmar:str = Field( description="Name of grammar points covered, no explanation. E.g. 'Present Simple', 'Past Perfect', 'Zero Conditional'. ")
    Form:str = Field( description="The form of the grammar point, including any relevant rules or structures.")
    Usage:str = Field( description="How the grammar point is used in context, with examples from the transcript.")
class StudentFeedback(BaseModel):
    lesson_summary:str = Field( description="A brief summary of the lesson content.")
    grammar_points:list[GrammarPoint] = Field( description="A list of grammar points covered in the lesson.")
    positive_feedback:str = Field( description="Specific moments during the lesson where the student performed well or showed improvement.")
    vocab_items:list[VocabItem] = Field( description="A list of vocabulary items introduced in the lesson.")
    corrections:list[Corrections] = Field( description="A list of corrections made to the student's work.")
    improvement_areas:str = Field( description="Areas where the student can improve, including specific skills or topics to focus on.")
student_schema = StudentFeedback.model_json_schema()
