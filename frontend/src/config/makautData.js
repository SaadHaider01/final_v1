/**
 * MAKAUT (Maulana Abul Kalam Azad University of Technology)
 * Static curriculum hierarchy — used to pre-populate cascading dropdowns.
 *
 * Structure: BOS → Department → Program → Semester
 * Subjects are free-text (entered per upload).
 *
 * Extend this file as needed when adding more universities.
 */

export const CURRICULUM = [
    {
        bos: "MAKAUT – Engineering",
        departments: [
            {
                name: "Computer Science & Engineering",
                short: "CSE",
                programs: [
                    {
                        name: "B.Tech CSE",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech CSE",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
            {
                name: "Information Technology",
                short: "IT",
                programs: [
                    {
                        name: "B.Tech IT",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech IT",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
            {
                name: "Artificial Intelligence & Machine Learning",
                short: "AIML",
                programs: [
                    {
                        name: "B.Tech AIML",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                ],
            },
            {
                name: "Data Science",
                short: "DS",
                programs: [
                    {
                        name: "B.Tech DS",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                ],
            },
            {
                name: "Computer Science & Business Systems",
                short: "CSBS",
                programs: [
                    {
                        name: "B.Tech CSBS",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                ],
            },
            {
                name: "Electronics & Communication Engineering",
                short: "ECE",
                programs: [
                    {
                        name: "B.Tech ECE",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech ECE",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
            {
                name: "Electrical Engineering",
                short: "EE",
                programs: [
                    {
                        name: "B.Tech EE",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech EE",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
            {
                name: "Mechanical Engineering",
                short: "ME",
                programs: [
                    {
                        name: "B.Tech ME",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech ME",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
            {
                name: "Civil Engineering",
                short: "CE",
                programs: [
                    {
                        name: "B.Tech CE",
                        semesters: ["1", "2", "3", "4", "5", "6", "7", "8"],
                    },
                    {
                        name: "M.Tech CE",
                        semesters: ["1", "2", "3", "4"],
                    },
                ],
            },
        ],
    },
    // ── Extend here for other universities / BOS ───────────────────────────
    // {
    //   bos: "XYZ University – Arts",
    //   departments: [ ... ],
    // },
];

// ── Derived lookup helpers ─────────────────────────────────────────────────

export const getBosOptions = () => CURRICULUM.map(b => b.bos);

export const getDeptOptions = (bos) => {
    const entry = CURRICULUM.find(b => b.bos === bos);
    return entry ? entry.departments.map(d => d.name) : [];
};

export const getProgramOptions = (bos, dept) => {
    const bosEntry = CURRICULUM.find(b => b.bos === bos);
    if (!bosEntry) return [];
    const deptEntry = bosEntry.departments.find(d => d.name === dept);
    return deptEntry ? deptEntry.programs.map(p => p.name) : [];
};

export const getSemesterOptions = (bos, dept, program) => {
    const bosEntry = CURRICULUM.find(b => b.bos === bos);
    if (!bosEntry) return [];
    const deptEntry = bosEntry.departments.find(d => d.name === dept);
    if (!deptEntry) return [];
    const progEntry = deptEntry.programs.find(p => p.name === program);
    return progEntry ? progEntry.semesters : [];
};
