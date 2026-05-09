# ANALYSIS AND DESIGN DOCUMENT

## REQUIREMENTS

Today, you are going to build a todo list website. This is a right of passage for any developer.

You can choose the type of todo list you want to build. It could be as simple as a website where you can list some items and cross them out. Or as complex as a Kanban-style task list like Trello.

Here is a website for inspiration:

https://flask.io/new

 ## FUNCTIONAL ANALYSIS

1. Design and prototype the structure(pages to create) of the website at layout level
2. Specify what are the main website functionalities.
3. Design the database structure.

Other details. We need to use the SQLAlchemy python library so to call a PostreSQL Database to store our data. The table needed will be 3.  

### Database Design 

The table "users" that contains all the data necessary for each user with the fields 
| Column Name  | Data type     |Nullable  |Key          |Notes                    |
| ------------ | ------------- | -------- | ----------- | ----------------------- |
| UserId       | integer       |          | Primary key |                         | 
| FirstName    | string(100)   | False    |             |                         | 
| LastName     | string(100)   | False    |             |                         | 
| EmailAddress | string(255)   | False    |             |                         | 
| Password     | string(255)   | False    |             |                         | 
| CreatedAt    | DateTime      |          |             | User's Creation date    |
-----------------------------------------------------------------------------------

The table "lists":   
| Column Name  | Data type    | Nullable  | Key           |Notes                   |
| ------------ | ------------ | --------- | ------------- | ---------------------- |      
| ListId       | Integer      |           |  Primary Key  |                        |
| UserId       | Integer      |  False    |  Foreign Key  |                        |
| Title        | string(200)  |  False    |               |                        | 
| CreatedAt    | Datetime     |  False    |               | Date of list creation  |
------------------------------------------------------------------------------------

The table "Task"
| Column Name  | Data type     | Nullable  | Key          | Notes                   |
| ------------ | ------------- | --------- | ------------ | ----------------------- |                   
| TaskId       | Integer       |           | Primary Key  |                         |
| ListId       | Integer       | False     | Foreign Key  |                         |
| TaskText     | string(500)   | False     |              |                         |  
| Isdone       | boolean       | False     |              | Default=False           | 
| CreatedAt    | False         |           |              | Date of task creation   |

### Claude Code Prompt
I have created a website layout with Claude Design to use coupled with Claude. 

**Here's the prompt.**
Create a Flask website keeping into consideration the README.md file present in this folder with the exlusion of test and production parts. These are the istruction at layout level --> Fetch this design file, read its readme, and implement the relevant aspects of the design. https://api.anthropic.com/v1/design/h/xdnmMtNZTUZtOSmydbfTnA?open_file=Todo+List.html


## DESIGN AND IMPLEMENTATION DETAILS

TO DO LIST. As we enter into more detail of the project, we need to do for the best website outcomes in terms of layout, maintenance and usability. 

### At Code level 
I divided the project into smaller parts:

-  Connect the Flask application with the SQLite database.
-  Create routes to display lists information.
-  Design HTML templates using Bootstrap for a clean UI.
-  Display tasks dynamically using Jinja templating.
-  Add forms for adding new tasks.
-  Implement delete functionality for lists and single tasks.
-  Improve navigation and overall styling.

TO DO
1. Add some diagnostic features to make visibile the database connection problems and fallback.
2. Make the code easily debuggable and maintenable


### Test environment
1. Prepare a local Postgres sql Container for local test. 
2. Test it locally in a development environment.

### Production relaese  
-  After the positive test locally, prepare the folder /vendor to deploy into the Production Linux environment. 
-  Install the source code into production, make all the settings (.htaccess, environmental variabile, flask setup)



