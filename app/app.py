from flask import Flask, render_template, request, redirect, url_for, flash
import cx_Oracle

app = Flask(__name__)
app.secret_key = 'tts_secret_2026'

# ── DB CONNECTION ────────────────────────────────────────────────────────────
# Change these if your credentials differ
DB_USER = "system"
DB_PASS = "1250"

def get_db():
    try:
        dsn = cx_Oracle.makedsn("LAPTOP-8GD4BRP0", 1521, service_name="XEPDB1")
        conn = cx_Oracle.connect(
            user="system",
            password="1250",
            dsn=dsn
        )
        return conn
    except Exception as e:
        print("DB ERROR:", e)
        return None

def rows_to_dicts(cursor):
    """Convert cursor rows → list of dicts using column names."""
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

# ── HELPERS ──────────────────────────────────────────────────────────────────

def load_lookups(cursor):
    """Fetch all dropdown data needed for forms."""
    cursor.execute("SELECT class_id, class_name, semester FROM class_batch ORDER BY class_name")
    classes = rows_to_dicts(cursor)

    cursor.execute("SELECT subject_id, subject_name, credits FROM subject ORDER BY subject_name")
    subjects = rows_to_dicts(cursor)

    cursor.execute("SELECT faculty_id, faculty_name, designation FROM faculty ORDER BY faculty_name")
    faculty = rows_to_dicts(cursor)

    cursor.execute("SELECT room_id, room_number, capacity FROM classroom ORDER BY room_number")
    classrooms = rows_to_dicts(cursor)

    cursor.execute("SELECT slot_id, day, start_time, end_time FROM timeslot ORDER BY DECODE(day,'Monday',1,'Tuesday',2,'Wednesday',3,'Thursday',4,'Friday',5), start_time")
    timeslots = rows_to_dicts(cursor)

    return classes, subjects, faculty, classrooms, timeslots

# ── ROUTES ───────────────────────────────────────────────────────────────────
@app.route('/check_connection')
def check_connection():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT 'CONNECTED_OK' FROM dual")
        result = cur.fetchone()[0]

        cur.close()
        conn.close()

        return f"Flask DB Status: {result}"

    except Exception as e:
        return f"Connection FAILED: {str(e)}"


@app.route('/')
def index():
    conn = get_db()
    if not conn:
        return "Database connection failed"

    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM timetable")
    total_entries = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM faculty")
    total_faculty = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM class_batch")
    total_classes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM subject")
    total_subjects = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template('index.html',
        total_entries=total_entries,
        total_faculty=total_faculty,
        total_classes=total_classes,
        total_subjects=total_subjects)

#check data 
@app.route('/check_data')
def check_data():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT faculty_id, faculty_name FROM faculty")
    data = cur.fetchall()

    return str(data)
# ── VIEW TIMETABLE ────────────────────────────────────────────────────────────

@app.route('/timetable')
def view_timetable():
    filter_class   = request.args.get('class_id',   '')
    filter_faculty = request.args.get('faculty_id', '')
    filter_room    = request.args.get('room_id',    '')

    conn = get_db()
    if not conn:
        return "Database connection failed"
    cur  = conn.cursor()

    sql = """
        SELECT tt.timetable_id,
               cb.class_name,   cb.class_id,
               s.subject_name,
               f.faculty_name,  f.faculty_id,
               r.room_number,   r.room_id,
               ts.day, ts.start_time, ts.end_time, ts.slot_id
        FROM   timetable tt
        JOIN   class_batch cb ON tt.class_id   = cb.class_id
        JOIN   subject      s  ON tt.subject_id = s.subject_id
        JOIN   faculty      f  ON tt.faculty_id = f.faculty_id
        JOIN   classroom    r  ON tt.room_id    = r.room_id
        JOIN   timeslot     ts ON tt.slot_id    = ts.slot_id
        WHERE  1=1
    """
    params = {}
    if filter_class:
        sql += " AND tt.class_id = :cid";   params['cid'] = int(filter_class)
    if filter_faculty:
        sql += " AND tt.faculty_id = :fid"; params['fid'] = int(filter_faculty)
    if filter_room:
        sql += " AND tt.room_id = :rid";    params['rid'] = int(filter_room)

    sql += " ORDER BY DECODE(ts.day,'Monday',1,'Tuesday',2,'Wednesday',3,'Thursday',4,'Friday',5), ts.start_time"

    cur.execute(sql, params)
    entries = rows_to_dicts(cur)

    classes, subjects, faculty, classrooms, timeslots = load_lookups(cur)
    cur.close(); conn.close()

    return render_template('timetable.html',
        entries=entries, classes=classes, faculty=faculty,
        classrooms=classrooms,
        filter_class=filter_class,
        filter_faculty=filter_faculty,
        filter_room=filter_room)

# ── ADD ENTRY ─────────────────────────────────────────────────────────────────
@app.route('/timetable/add', methods=['GET', 'POST'])
def add_entry():
    conn = get_db()
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()

    if request.method == 'POST':
        class_id   = int(request.form['class_id'])
        subject_id = int(request.form['subject_id'])
        faculty_id = int(request.form['faculty_id'])
        room_id    = int(request.form['room_id'])
        slot_id    = int(request.form['slot_id'])

        try:
            # CALL PROCEDURE → trigger handles conflicts
            cur.callproc('add_timetable_entry',
                         [class_id, subject_id, faculty_id, room_id, slot_id])

            conn.commit()

            flash(" Entry added successfully!", "success")
            cur.close()
            conn.close()
            return redirect(url_for('view_timetable'))

        except cx_Oracle.DatabaseError as e:
            error_msg = str(e)

            if 'FACULTY_CONFLICT' in error_msg:
                flash("Faculty already has a class in this slot!", "error")

            elif 'ROOM_CONFLICT' in error_msg:
                flash(" Room already booked in this slot!", "error")

            elif 'CLASS_CONFLICT' in error_msg:
                flash(" Class already has a subject in this slot!", "error")

            elif 'DUPLICATE_ENTRY' in error_msg:
                flash(" Duplicate entry!", "error")

            else:
                flash(f" Database error: {error_msg}", "error")

    classes, subjects, faculty, classrooms, timeslots = load_lookups(cur)
    cur.close()
    conn.close()

    return render_template('add_entry.html',
        classes=classes, subjects=subjects,
        faculty=faculty, classrooms=classrooms, timeslots=timeslots)


# ── DELETE ENTRY ──────────────────────────────────────────────────────────────

@app.route('/timetable/delete/<int:entry_id>')
def delete_entry(entry_id):
    conn = get_db()
    if not conn:
        return "Database connection failed"
    cur  = conn.cursor()
    cur.execute("DELETE FROM timetable WHERE timetable_id = :id", {'id': entry_id})
    conn.commit()
    cur.close(); conn.close()
    flash("Entry deleted.", "success")
    return redirect(url_for('view_timetable'))

# ── FACULTY WORKLOAD ──────────────────────────────────────────────────────────

@app.route('/workload')
def faculty_workload():
    conn = get_db()
    if not conn:
        return "Database connection failed"
    cur  = conn.cursor()

    cur.execute("""
        SELECT f.faculty_id,
               f.faculty_name,
               get_faculty_hours(f.faculty_id) AS total_hours,
               LISTAGG(DISTINCT s.subject_name, ', ')
                   WITHIN GROUP (ORDER BY s.subject_name) AS subjects,
               LISTAGG(DISTINCT cb.class_name, ', ')
                   WITHIN GROUP (ORDER BY cb.class_name)  AS classes
        FROM   faculty f
        LEFT JOIN timetable tt ON f.faculty_id = tt.faculty_id
        LEFT JOIN subject    s  ON tt.subject_id = s.subject_id
        LEFT JOIN class_batch cb ON tt.class_id  = cb.class_id
        GROUP BY f.faculty_id, f.faculty_name
        ORDER BY total_hours DESC
    """)
    rows = rows_to_dicts(cur)
    cur.close(); conn.close()

    workload = []
    for r in rows:
        hours = r['total_hours'] or 0
        workload.append({
            'faculty_name': r['faculty_name'],
            'hours':        int(hours),
            'subjects':     r['subjects'].split(', ') if r['subjects'] else [],
            'classes':      r['classes'].split(', ')  if r['classes']  else [],
            'load':         'Heavy' if hours >= 3 else 'Moderate' if hours == 2 else 'Light'
        })

    return render_template('workload.html', workload=workload)

# ── FREE SLOT FINDER ──────────────────────────────────────────────────────────

@app.route('/freeslots')
def free_slots():
    sel_faculty = request.args.get('faculty_id', '')
    sel_class   = request.args.get('class_id',   '')
    sel_room    = request.args.get('room_id',    '')
    results     = []

    conn = get_db()
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur  = conn.cursor()

    if sel_faculty or sel_class or sel_room:
        cur.execute("""
            SELECT slot_id, day, start_time, end_time
            FROM   timeslot
            ORDER BY DECODE(day,'Monday',1,'Tuesday',2,'Wednesday',3,'Thursday',4,'Friday',5),
                     start_time
        """)
        all_slots = rows_to_dicts(cur)

        for slot in all_slots:
            sid     = slot['slot_id']
            taken   = False
            reasons = []

            if sel_faculty:
                cur.execute("SELECT COUNT(*) FROM timetable WHERE faculty_id=:f AND slot_id=:s",
                            {'f': int(sel_faculty), 's': sid})
                if cur.fetchone()[0] > 0:
                    taken = True; reasons.append("Faculty busy")

            if sel_class:
                cur.execute("SELECT COUNT(*) FROM timetable WHERE class_id=:c AND slot_id=:s",
                            {'c': int(sel_class), 's': sid})
                if cur.fetchone()[0] > 0:
                    taken = True; reasons.append("Class busy")

            if sel_room:
                cur.execute("SELECT COUNT(*) FROM timetable WHERE room_id=:r AND slot_id=:s",
                            {'r': int(sel_room), 's': sid})
                if cur.fetchone()[0] > 0:
                    taken = True; reasons.append("Room occupied")

            results.append({**slot, 'available': not taken, 'reasons': reasons})

    classes, _, faculty, classrooms, _ = load_lookups(cur)
    cur.close(); conn.close()

    return render_template('freeslots.html',
        results=results, faculty=faculty, classes=classes, classrooms=classrooms,
        sel_faculty=sel_faculty, sel_class=sel_class, sel_room=sel_room)

# ── MANAGE PAGES ──────────────────────────────────────────────────────────────

@app.route('/manage/departments')
def manage_departments():
    conn = get_db(); 
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur.execute("SELECT dept_id, dept_name, building FROM department ORDER BY dept_id")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Departments", items=items,
        fields=["dept_id","dept_name","building"])

@app.route('/manage/faculty')
def manage_faculty():
    conn = get_db();
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur.execute("""SELECT f.faculty_id, f.faculty_name, f.designation, d.dept_name
                   FROM faculty f JOIN department d ON f.dept_id=d.dept_id
                   ORDER BY f.faculty_id""")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Faculty", items=items,
        fields=["faculty_id","faculty_name","designation","dept_name"])

@app.route('/manage/subjects')
def manage_subjects():
    conn = get_db();
    
    if not conn:
        return "Database connection failed" 
    cur = conn.cursor()
    cur.execute("""SELECT s.subject_id, s.subject_name, s.credits, d.dept_name
                   FROM subject s JOIN department d ON s.dept_id=d.dept_id
                   ORDER BY s.subject_id""")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Subjects", items=items,
        fields=["subject_id","subject_name","credits","dept_name"])

@app.route('/manage/classes')
def manage_classes():
    conn = get_db();
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur.execute("""SELECT c.class_id, c.class_name, c.semester, d.dept_name
                   FROM class_batch c JOIN department d ON c.dept_id=d.dept_id
                   ORDER BY c.class_id""")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Classes", items=items,
        fields=["class_id","class_name","semester","dept_name"])

@app.route('/manage/classrooms')
def manage_classrooms():
    conn = get_db();
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur.execute("SELECT room_id, room_number, capacity FROM classroom ORDER BY room_id")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Classrooms", items=items,
        fields=["room_id","room_number","capacity"])

@app.route('/manage/timeslots')
def manage_timeslots():
    conn = get_db();
    if not conn:
        return "Database connection failed"
    cur = conn.cursor()
    cur.execute("""SELECT slot_id, day, start_time, end_time FROM timeslot
                   ORDER BY DECODE(day,'Monday',1,'Tuesday',2,'Wednesday',3,'Thursday',4,'Friday',5),
                            start_time""")
    items = rows_to_dicts(cur)
    cur.close(); conn.close()
    return render_template('manage.html', title="Time Slots", items=items,
        fields=["slot_id","day","start_time","end_time"])

if __name__ == '__main__':
    app.run(debug=True)
