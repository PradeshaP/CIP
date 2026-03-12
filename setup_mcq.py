"""
setup_mcq.py
────────────
Run this ONCE before starting the app to:
  1. Verify PostgreSQL connection
  2. Create all tables (mcq_sessions, mcq_questions, mcq_participants, mcq_answers)
  3. Optionally insert a sample MCQ set for testing

Usage:
  python setup_mcq.py

  # With custom DB URL:
  POSTGRES_HOST=myhost POSTGRES_USER=myuser POSTGRES_PASSWORD=mypass python setup_mcq.py

  # Skip sample data:
  python setup_mcq.py --no-sample
"""

import sys
import os

def main():
    insert_sample = "--no-sample" not in sys.argv

    print("=" * 60)
    print("  MCQ MODULE — Database Setup")
    print("=" * 60)

    # ── Step 1: Test connection ─────────────────────────────────────────
    print("\n[1/3] Testing PostgreSQL connection…")
    try:
        import mcq_database as db
    except ImportError:
        print("ERROR: mcq_database.py not found. Place both files in the same folder.")
        sys.exit(1)

    ok, msg = db.test_connection()
    if not ok:
        print(f"FAILED: {msg}")
        print()
        print("Check these environment variables:")
        print("  POSTGRES_HOST     (default: localhost)")
        print("  POSTGRES_PORT     (default: 5432)")
        print("  POSTGRES_DB       (default: interview_coach)")
        print("  POSTGRES_USER     (default: postgres)")
        print("  POSTGRES_PASSWORD (required!)")
        sys.exit(1)

    print(f"OK: {msg}")

    # ── Step 2: Create schema ───────────────────────────────────────────
    print("\n[2/3] Creating schema (tables + indexes)…")
    ok = db.init_db()
    if not ok:
        print("FAILED: Could not create schema. Check DB permissions.")
        sys.exit(1)
    print("OK: Schema ready.")

    # ── Step 3: Optional sample data ───────────────────────────────────
    if insert_sample:
        print("\n[3/3] Inserting sample MCQ session for testing…")

        sample_questions = [
            {
                "question_text":  "What is the time complexity of binary search on a sorted array of n elements?",
                "option_a":       "O(n)",
                "option_b":       "O(log n)",
                "option_c":       "O(n log n)",
                "option_d":       "O(1)",
                "correct_option": "b",
                "explanation":    "Binary search halves the search space each step, giving O(log n). "
                                  "O(n) would be linear search; O(n log n) is merge sort complexity.",
                "skill":          "DSA",
                "category":       "DSA & CS Fundamentals",
                "difficulty":     "easy",
            },
            {
                "question_text":  "Which of the following correctly describes a Python list comprehension?",
                "option_a":       "It creates a generator object that yields elements lazily",
                "option_b":       "It creates a new list by applying an expression to each item in an iterable",
                "option_c":       "It modifies an existing list in place",
                "option_d":       "It creates a dictionary from key-value pairs",
                "correct_option": "b",
                "explanation":    "List comprehensions produce a new list. Generators use () not []. "
                                  "In-place modification is done with methods like .append(). "
                                  "Dict comprehensions use {} with key:value syntax.",
                "skill":          "Python",
                "category":       "Programming Languages",
                "difficulty":     "easy",
            },
            {
                "question_text":  "What happens if you define a Python function with a mutable default argument?",
                "option_a":       "The default value is reset to empty on each function call",
                "option_b":       "A TypeError is raised at function definition time",
                "option_c":       "The mutable object is shared across all calls that use the default",
                "option_d":       "Python automatically creates a copy of the object for each call",
                "correct_option": "c",
                "explanation":    "Default argument values are evaluated once at function definition. "
                                  "A mutable default like [] is shared across all calls, so "
                                  "appending to it in one call affects subsequent calls. "
                                  "Use None as default and create the object inside the function.",
                "skill":          "Python",
                "category":       "Programming Languages",
                "difficulty":     "hard",
            },
            {
                "question_text":  "In SQL, what is the difference between WHERE and HAVING?",
                "option_a":       "WHERE filters rows after grouping; HAVING filters before grouping",
                "option_b":       "WHERE filters rows before grouping; HAVING filters groups after GROUP BY",
                "option_c":       "They are interchangeable and produce identical results",
                "option_d":       "WHERE works only on numeric columns; HAVING works on all types",
                "correct_option": "b",
                "explanation":    "WHERE applies to individual rows before any GROUP BY. "
                                  "HAVING filters the resulting groups, so it can use aggregate functions "
                                  "like HAVING COUNT(*) > 5. WHERE cannot use aggregate functions.",
                "skill":          "SQL",
                "category":       "Databases",
                "difficulty":     "medium",
            },
            {
                "question_text":  "Which HTTP status code correctly indicates that a resource was successfully created?",
                "option_a":       "200 OK",
                "option_b":       "204 No Content",
                "option_c":       "201 Created",
                "option_d":       "202 Accepted",
                "correct_option": "c",
                "explanation":    "201 Created is the correct response for a POST that creates a resource. "
                                  "200 is for successful GET/PUT. 204 means success with no response body. "
                                  "202 means the request was accepted but processing is not yet complete.",
                "skill":          "REST APIs",
                "category":       "Backend Development",
                "difficulty":     "easy",
            },
        ]

        sid = db.create_session(
            title           = "Sample Test Session",
            time_limit_mins = 15,
            skill_tags      = ["Python", "SQL", "DSA", "REST APIs"],
            created_by      = "setup_script",
        )
        count = db.insert_questions(sid, sample_questions)
        print(f"OK: Sample session created ({count} questions).")
        print(f"    Session ID: {sid}")
    else:
        print("\n[3/3] Skipping sample data (--no-sample flag set).")

    # ── Summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Setup complete! Run the app with:")
    print("    streamlit run mcq_app.py")
    print()
    print("  Admin password (change MCQ_ADMIN_PASSWORD env var):")
    print("    admin123")
    print("=" * 60)


if __name__ == "__main__":
    main()