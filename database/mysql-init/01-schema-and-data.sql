CREATE TABLE IF NOT EXISTS Department (
  department_id INT PRIMARY KEY,
  department_name VARCHAR(80) NOT NULL UNIQUE,
  location VARCHAR(80) NOT NULL
);

CREATE TABLE IF NOT EXISTS Employee (
  employee_id INT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  department VARCHAR(80) NOT NULL,
  salary DECIMAL(12, 2) NOT NULL,
  joining_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS Students (
  student_id INT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  course VARCHAR(120) NOT NULL,
  cgpa DECIMAL(3, 2) NOT NULL,
  faculty_id INT
);

INSERT IGNORE INTO Department (department_id, department_name, location) VALUES
  (1, 'Engineering', 'Bengaluru'),
  (2, 'Human Resources', 'Mumbai'),
  (3, 'Finance', 'Delhi'),
  (4, 'Sales', 'Pune'),
  (5, 'Operations', 'Hyderabad');

INSERT IGNORE INTO Employee (employee_id, name, email, department, salary, joining_date) VALUES
  (1, 'Aarav Sharma', 'aarav.sharma@example.com', 'Engineering', 92000.00, '2020-01-15'),
  (2, 'Isha Mehta', 'isha.mehta@example.com', 'Engineering', 88000.00, '2021-03-22'),
  (3, 'Rohan Gupta', 'rohan.gupta@example.com', 'Engineering', 76000.00, '2022-06-10'),
  (4, 'Neha Kapoor', 'neha.kapoor@example.com', 'Engineering', 83000.00, '2019-11-05'),
  (5, 'Kabir Rao', 'kabir.rao@example.com', 'Engineering', 71000.00, '2023-02-14'),
  (6, 'Maya Nair', 'maya.nair@example.com', 'Human Resources', 64000.00, '2020-07-18'),
  (7, 'Vivaan Singh', 'vivaan.singh@example.com', 'Human Resources', 59000.00, '2021-09-01'),
  (8, 'Anika Joshi', 'anika.joshi@example.com', 'Human Resources', 62000.00, '2022-12-12'),
  (9, 'Dev Patel', 'dev.patel@example.com', 'Human Resources', 57000.00, '2023-05-20'),
  (10, 'Sara Khan', 'sara.khan@example.com', 'Human Resources', 68000.00, '2018-04-03'),
  (11, 'Arjun Reddy', 'arjun.reddy@example.com', 'Finance', 79000.00, '2019-08-25'),
  (12, 'Priya Menon', 'priya.menon@example.com', 'Finance', 85000.00, '2020-10-30'),
  (13, 'Karan Malhotra', 'karan.malhotra@example.com', 'Finance', 73000.00, '2021-01-09'),
  (14, 'Nisha Verma', 'nisha.verma@example.com', 'Finance', 69000.00, '2022-07-07'),
  (15, 'Aditya Bose', 'aditya.bose@example.com', 'Finance', 91000.00, '2018-06-16'),
  (16, 'Meera Iyer', 'meera.iyer@example.com', 'Sales', 66000.00, '2020-02-11'),
  (17, 'Yash Agarwal', 'yash.agarwal@example.com', 'Sales', 72000.00, '2021-04-19'),
  (18, 'Tara Das', 'tara.das@example.com', 'Sales', 61000.00, '2022-08-24'),
  (19, 'Om Kulkarni', 'om.kulkarni@example.com', 'Sales', 70000.00, '2019-12-02'),
  (20, 'Riya Chatterjee', 'riya.chatterjee@example.com', 'Sales', 75000.00, '2023-03-13'),
  (21, 'Sahil Jain', 'sahil.jain@example.com', 'Operations', 63000.00, '2020-05-26'),
  (22, 'Diya Shah', 'diya.shah@example.com', 'Operations', 67000.00, '2021-11-17'),
  (23, 'Manav Bhat', 'manav.bhat@example.com', 'Operations', 60000.00, '2022-09-29'),
  (24, 'Aditi Pillai', 'aditi.pillai@example.com', 'Operations', 74000.00, '2019-10-21'),
  (25, 'Krish Sethi', 'krish.sethi@example.com', 'Operations', 58000.00, '2023-06-08');

INSERT IGNORE INTO Students (student_id, name, email, course, cgpa, faculty_id) VALUES
  (1, 'Ananya Sen', 'ananya.sen@example.com', 'Computer Science', 9.40, 101),
  (2, 'Rahul Nanda', 'rahul.nanda@example.com', 'Data Science', 8.70, 102),
  (3, 'Sia Thomas', 'sia.thomas@example.com', 'Cybersecurity', 9.10, 103),
  (4, 'Aryan Mishra', 'aryan.mishra@example.com', 'Artificial Intelligence', 8.90, 101),
  (5, 'Kiara George', 'kiara.george@example.com', 'Cloud Computing', 8.20, 104),
  (6, 'Rudra Gill', 'rudra.gill@example.com', 'Computer Science', 7.90, 102),
  (7, 'Myra Saxena', 'myra.saxena@example.com', 'Data Science', 9.30, 103),
  (8, 'Neil Bansal', 'neil.bansal@example.com', 'Cybersecurity', 8.10, 104),
  (9, 'Avni Roy', 'avni.roy@example.com', 'Artificial Intelligence', 9.60, 101),
  (10, 'Reyansh Dutta', 'reyansh.dutta@example.com', 'Cloud Computing', 7.80, 102),
  (11, 'Tisha Jain', 'tisha.jain@example.com', 'Computer Science', 8.50, 103),
  (12, 'Vihaan Shah', 'vihaan.shah@example.com', 'Data Science', 8.00, 104),
  (13, 'Zoya Ali', 'zoya.ali@example.com', 'Cybersecurity', 9.20, 101),
  (14, 'Ishaan Paul', 'ishaan.paul@example.com', 'Artificial Intelligence', 8.60, 102),
  (15, 'Mahi Suri', 'mahi.suri@example.com', 'Cloud Computing', 7.70, 103),
  (16, 'Laksh Rao', 'laksh.rao@example.com', 'Computer Science', 8.80, 104),
  (17, 'Aisha Khan', 'aisha.khan@example.com', 'Data Science', 9.00, 101),
  (18, 'Parth Sinha', 'parth.sinha@example.com', 'Cybersecurity', 7.60, 102),
  (19, 'Naira Chopra', 'naira.chopra@example.com', 'Artificial Intelligence', 9.50, 103),
  (20, 'Dhruv Arora', 'dhruv.arora@example.com', 'Cloud Computing', 8.30, 104),
  (21, 'Esha Bajaj', 'esha.bajaj@example.com', 'Computer Science', 8.40, 101),
  (22, 'Kunal Puri', 'kunal.puri@example.com', 'Data Science', 7.50, 102),
  (23, 'Pihu Anand', 'pihu.anand@example.com', 'Cybersecurity', 9.70, 103),
  (24, 'Harsh Vora', 'harsh.vora@example.com', 'Artificial Intelligence', 8.25, 104),
  (25, 'Rhea Kapoor', 'rhea.kapoor@example.com', 'Cloud Computing', 8.95, 101);

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'sql_app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON sql_generator_mysql.* TO 'sql_app_user'@'%';
GRANT ALL PRIVILEGES ON `workspace\_%`.* TO 'sql_app_user'@'%';
FLUSH PRIVILEGES;
