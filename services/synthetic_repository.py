from dataclasses import dataclass
from uuid import UUID

WORK_AREAS = (
    'Central Government', 'Critical National Infrastructure', 'Defence',
    'IdentityE2E', 'Law Enforcement (including Datalynx, Digital Forensics and PDS)',
    'National Security & Intelligence', 'IIG-wide',
)

@dataclass(frozen=True)
class Survey:
    slug: str
    label: str
    financial_year: str
    quarter: str
    date: str
    responses: int
    status: str
    analysis_status: str
    version: str = 'v1.0'

@dataclass(frozen=True)
class Question:
    slug: str
    text: str
    latest_positive: int
    movement: int
    response_type: str = 'agreement'
    metric_label: str = 'positive'
    comparable: bool = True
    aliases: tuple[str, ...] = ()

@dataclass(frozen=True)
class Theme:
    slug: str
    name: str
    description: str
    prevalence: int
    movement: int
    responses: int
    trend: str
    review_state: str

@dataclass(frozen=True)
class Employee:
    id: UUID
    name: str
    role: str
    surveys: int
    themes: tuple[str, ...]
    movement: int
    indicator: str

SURVEYS = (
    Survey('fy24-q1','FY2024 Q1','FY2024','Q1','2023-06-30',118,'Closed','Completed'),
    Survey('fy24-q2','FY2024 Q2','FY2024','Q2','2023-09-30',121,'Closed','Completed'),
    Survey('fy24-q3','FY2024 Q3','FY2024','Q3','2023-12-31',124,'Closed','Completed'),
    Survey('fy24-q4','FY2024 Q4','FY2024','Q4','2024-03-31',127,'Closed','Completed'),
    Survey('fy25-q1','FY2025 Q1','FY2025','Q1','2024-06-30',132,'Closed','Completed'),
    Survey('fy25-q2','FY2025 Q2','FY2025','Q2','2024-09-30',136,'Closed','Completed'),
    Survey('fy25-q3','FY2025 Q3','FY2025','Q3','2024-12-31',139,'Closed','Failed'),
    Survey('fy25-q4','FY2025 Q4','FY2025','Q4','2025-03-31',144,'Closed','Pending'),
)
QUESTIONS = (
    Question('happy-at-iig','I am happy at IIG',74,5),
    Question('supported-at-work','I feel supported at work',72,6),
    Question('role-expectations','I understand my role and what\'s expected of me',78,4),
    Question('tools-and-resources','I have access to the tools and resources I need to do my job well',69,-3),
    Question('future-of-work','I feel excited about the future of my work',65,7),
    Question('iig-community','I feel part of the IIG community',71,3),
    Question('primary-area','What is your primary area of work?',34,1,'choice','largest group',False),
    Question('work-experience-influence','What influenced your answers above?',81,4,'written','response rate',False),
    Question('training-days-used','Approximately how many training days have you used in the last 12 months?',48,6,'numeric','3+ days',True),
    Question('identify-learning-opportunities','Do you feel you have a clear understanding of how to identify training or learning opportunities?',73,8,'binary','yes',True),
    Question('training-time-plans','Do you know what you would like to use your training time for?',67,5,'binary','yes',True),
    Question('training-barriers','What are the main barriers preventing you from using your training time?',46,-4,'multiple_choice','most selected',False),
    Question('training-barrier-detail','Please provide any additional detail on the barriers you selected above (optional):',58,3,'written','response rate',False),
    Question('training-support','What would help you make better use of your training time?',76,5,'written','response rate',False),
    Question('prioritising-training','How comfortable do you feel prioritising training over project work when time allows?',61,-2,'rating','comfortable',True),
    Question('accessing-training','How easy is it to book or access training?',66,4,'rating','easy',True),
    Question('recommend-iig','Before you go, how likely are you to recommend IIG as a place to work?',70,3,'recommendation','promoter',True,('How likely are you to recommend IIG as a place to work?',)),
    Question('workplace-suggestions','Do you have any suggestions for improving our workplace?',64,2,'written','response rate',False),
)
THEMES = (
    Theme('workload-pressure','Workload pressure','Capacity, pace and competing priorities.',31,8,45,'increasing','Model-generated'),
    Theme('manager-support','Manager support','Availability, coaching and practical support.',27,-4,39,'decreasing','Human-confirmed'),
    Theme('career-growth','Career growth','Learning, progression and development pathways.',24,6,35,'increasing','Human-confirmed'),
    Theme('communication','Communication','Clarity, transparency and information flow.',22,0,32,'persistent','Model-generated'),
    Theme('team-connection','Team connection','Collaboration, belonging and peer relationships.',18,5,26,'new','Model-generated'),
)
_NAMES = ('Avery North','Blair Rowan','Cameron Vale','Devon Finch','Emery Stone','Finley Brook','Gray Linden','Harper Quill','Indigo Marsh','Jules Cedar','Kit Arden','Lane Winter')
EMPLOYEES = tuple(Employee(UUID(int=i+1), name, ('Analyst','Coordinator','Designer')[i%3], 6+(i%3), (THEMES[i%5].name, THEMES[(i+2)%5].name), (-8,-3,0,4,7)[i%5], ('Possible persistent concern' if i%4==0 else 'Possible improvement' if i%4==1 else 'Review indicator')) for i,name in enumerate(_NAMES))

class SyntheticAnalyticsRepository:
    def surveys(self): return SURVEYS
    def questions(self): return QUESTIONS
    def themes(self): return THEMES
    def employees(self): return EMPLOYEES
    def question(self, slug): return next((q for q in QUESTIONS if q.slug == slug), None)
    def theme(self, slug): return next((t for t in THEMES if t.slug == slug), None)
    def employee(self, employee_id): return next((e for e in EMPLOYEES if e.id == employee_id), None)

repository = SyntheticAnalyticsRepository()
