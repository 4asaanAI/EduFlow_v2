import React, { createContext, useContext, useState } from 'react';

const MOCK_USERS = {
  owner:   { id: 'user-owner-001', name: 'Aman',         role: 'owner',   initials: 'A'  },
  admin:   { id: 'user-admin-001', name: 'Priya Sharma', role: 'admin',   initials: 'PS' },
  teacher: { id: 'user-teacher-001', name: 'Rajesh Kumar', role: 'teacher', initials: 'RK' },
  student: { id: 'user-student-001', name: 'Rahul Singh',  role: 'student', initials: 'RS' },
};

const STORAGE_KEY = 'eduflow_user';

function loadStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(() => loadStoredUser());

  const login = (user) => {
    setCurrentUser(user);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  };

  const logout = () => {
    setCurrentUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  // Dev helper — switch role using mock users (for testing without re-login)
  const switchRole = (role) => {
    if (MOCK_USERS[role]) {
      const user = MOCK_USERS[role];
      setCurrentUser(user);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    }
  };

  return (
    <UserContext.Provider value={{ currentUser, login, logout, switchRole, MOCK_USERS }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used within UserProvider');
  return ctx;
}
