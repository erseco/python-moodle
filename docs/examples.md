# Examples

This page contains practical examples of using py-moodle for common tasks.

## Course Management Examples

### Create Multiple Courses

```bash
# Create courses from a list
for course in "Math 101" "Physics 201" "Chemistry 301"; do
    py-moodle courses create --fullname "$course" --shortname "$(echo $course | tr ' ' '-' | tr '[:upper:]' '[:lower:]')"
done
```

### Bulk Content Creation

```bash
# Add welcome labels to all sections of a course
course_id=2
for section in {1..5}; do
    py-moodle modules add label \
        --course-id $course_id \
        --section-id $section \
        --name "Section $section Welcome" \
        --intro "<h2>Welcome to Section $section</h2><p>This section covers important topics.</p>"
done
```

## File Management Examples

### Upload Multiple Files

```bash
# Upload all PDFs in a directory to a course folder
course_id=2
section_id=1
folder_name="Course Materials"

# Create the folder first
py-moodle modules add folder --course-id $course_id --section-id $section_id --name "$folder_name"

# Upload files (you'll need to get the folder ID from the output above)
for file in *.pdf; do
    py-moodle files upload --course-id $course_id --file "$file"
done
```

### SCORM Package Upload

```bash
# Upload and configure a SCORM package
py-moodle modules add scorm \
    --course-id 2 \
    --section-id 1 \
    --name "Interactive Lesson 1" \
    --path "./scorm-packages/lesson1.zip" \
    --intro "Complete this interactive lesson before the next class."
```

## Python Library Examples

### Automated Course Setup

```python
from py_moodle import MoodleSession
from py_moodle.course import create_course, list_courses
from py_moodle.module import add_label, add_folder

# Initialize session
ms = MoodleSession.get()

# Create a new course
course_data = {
    'fullname': 'Automated Course Setup Demo',
    'shortname': 'auto-demo-001',
    'categoryid': 1
}

course = create_course(ms.session, ms.settings.url, course_data, token=ms.token)
print(f"Created course: {course['id']}")

# Add welcome content
add_label(
    ms.session,
    ms.settings.url,
    course_id=course['id'],
    section_id=1,
    name="Course Welcome",
    intro="<h1>Welcome!</h1><p>This course was created automatically.</p>",
    token=ms.token
)

# Add a materials folder
add_folder(
    ms.session,
    ms.settings.url,
    course_id=course['id'],
    section_id=1,
    name="Course Materials",
    intro="All course materials will be stored here.",
    token=ms.token
)

print("Course setup completed!")
```

### Batch User Enrollment

```python
from py_moodle import MoodleSession
from py_moodle.user import list_users
from py_moodle.course import enroll_user

ms = MoodleSession.get()

# List of users to enroll
user_emails = ['student1@example.com', 'student2@example.com', 'student3@example.com']
course_id = 2

# Get all users
users = list_users(ms.session, ms.settings.url, token=ms.token)

# Create email to user ID mapping
email_to_id = {user['email']: user['id'] for user in users}

# Enroll users
for email in user_emails:
    if email in email_to_id:
        user_id = email_to_id[email]
        enroll_user(ms.session, ms.settings.url, course_id, user_id, token=ms.token)
        print(f"Enrolled {email} in course {course_id}")
    else:
        print(f"User {email} not found")
```

## Advanced Automation

### Complete Course Deployment

```python
import json
from py_moodle import MoodleSession
from py_moodle.course import create_course
from py_moodle.module import add_label, add_resource, add_scorm

# Load course configuration from JSON
with open('course_config.json', 'r') as f:
    config = json.load(f)

ms = MoodleSession.get()

# Create the course
course = create_course(ms.session, ms.settings.url, config['course'], token=ms.token)
print(f"Created course: {course['shortname']}")

# Add content according to configuration
for section_config in config['sections']:
    section_id = section_config['id']
    
    # Add section content
    for content in section_config['content']:
        if content['type'] == 'label':
            add_label(
                ms.session, ms.settings.url,
                course_id=course['id'],
                section_id=section_id,
                name=content['name'],
                intro=content['intro'],
                token=ms.token
            )
        elif content['type'] == 'scorm':
            add_scorm(
                ms.session, ms.settings.url,
                course_id=course['id'],
                section_id=section_id,
                name=content['name'],
                scorm_file=content['file'],
                token=ms.token
            )

print("Course deployment completed!")
```

Example `course_config.json`:

```json
{
  "course": {
    "fullname": "Introduction to Python Programming",
    "shortname": "python-intro-2024",
    "categoryid": 1
  },
  "sections": [
    {
      "id": 1,
      "content": [
        {
          "type": "label",
          "name": "Course Introduction",
          "intro": "<h2>Welcome to Python Programming!</h2><p>This course will teach you the basics of Python.</p>"
        },
        {
          "type": "scorm",
          "name": "Python Basics Interactive",
          "file": "./scorm/python-basics.zip"
        }
      ]
    }
  ]
}
```

## Troubleshooting Examples

### Debug Session Issues

```python
from py_moodle import MoodleSession

# Enable debug mode
ms = MoodleSession.get()
print(f"Session URL: {ms.settings.url}")
print(f"Session token: {ms.token[:10]}..." if ms.token else "No token")

# Test session validity
try:
    from py_moodle.course import list_courses
    courses = list_courses(ms.session, ms.settings.url, token=ms.token)
    print(f"Session valid - found {len(courses)} courses")
except Exception as e:
    print(f"Session error: {e}")
```

### Error Handling

```python
from py_moodle import MoodleSession
from py_moodle.course import create_course

ms = MoodleSession.get()

try:
    course_data = {
        'fullname': 'Test Course',
        'shortname': 'test-duplicate',  # This might already exist
        'categoryid': 1
    }
    
    course = create_course(ms.session, ms.settings.url, course_data, token=ms.token)
    print(f"Success: Created course {course['id']}")
    
except Exception as e:
    print(f"Error creating course: {e}")
    # Handle specific error cases
    if "shortname" in str(e).lower():
        print("Try using a unique shortname")
    elif "permission" in str(e).lower():
        print("Check your user permissions")
```
