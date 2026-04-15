const API_BASE = process.env.NODE_ENV === 'production' ? '/api/v1' : 'http://localhost:8000/api/v1';

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// Fetch CSRF cookie from Django on first load
let csrfReady = fetch(`${API_BASE}/csrf/`, { credentials: 'include' }).catch(() => {});

async function request(path, options = {}) {
  // Wait for CSRF cookie to be set
  await csrfReady;

  const config = {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
      ...options.headers,
    },
    ...options,
  };

  const res = await fetch(`${API_BASE}${path}`, config);

  if (res.status === 401 || res.status === 403) {
    // Not authenticated
    return { error: 'unauthorized', status: res.status };
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    // DRF returns field errors as {"field": ["message"]} — flatten them
    if (!data.error && typeof data === 'object') {
      const messages = Object.entries(data)
        .map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(', ') : val}`)
        .join('. ');
      return { error: messages || 'Request failed', status: res.status };
    }
    return { error: data.error || 'Request failed', status: res.status };
  }

  if (res.status === 204) return {};
  return res.json();
}

// Auth
export const auth = {
  register: (data) => request('/auth/register/', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/auth/login/', { method: 'POST', body: JSON.stringify(data) }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
};

// Profile
export const profile = {
  get: () => request('/profile/'),
  update: (data) => request('/profile/', { method: 'PATCH', body: JSON.stringify(data) }),
  saveLayout: (layout) => request('/profile/layout/', { method: 'PATCH', body: JSON.stringify({ custom_layout: layout }) }),
};

// Sections registry
export const sections = {
  list: () => request('/sections/'),
};

// Children
export const children = {
  list: () => request('/children/'),
  create: (data) => request('/children/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/children/${id}/`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/children/${id}/`, { method: 'DELETE' }),
};

// Events
export const events = {
  list: (params = '') => request(`/events/${params ? '?' + params : ''}`),
  create: (data) => request('/events/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/events/${id}/`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/events/${id}/`, { method: 'DELETE' }),
};

// Plans
export const plans = {
  generate: (date) => request('/plans/generate/', { method: 'POST', body: JSON.stringify(date ? { date } : {}) }),
  get: (date) => request(`/plans/${date}/`),
  swapMeal: (date, mealType) => request(`/plans/${date}/swap-meal/`, { method: 'POST', body: JSON.stringify({ meal_type: mealType }) }),
  substituteMeal: (date, mealType, ingredient) => request(`/plans/${date}/substitute-meal/`, { method: 'POST', body: JSON.stringify({ meal_type: mealType, ingredient }) }),
  changeMeal: (date, mealType, userRequest) => request(`/plans/${date}/change-meal/`, { method: 'POST', body: JSON.stringify({ meal_type: mealType, request: userRequest }) }),
  weekly: () => request('/plans/weekly/'),
  generateWeek: () => request('/plans/weekly/', { method: 'POST' }),
};

// Favourite meals
export const meals = {
  listFavourites: () => request('/meals/favourites/'),
  toggleFavourite: (mealName, mealType, description) => request('/meals/favourite/', { method: 'POST', body: JSON.stringify({ meal_name: mealName, meal_type: mealType, description }) }),
};

// Chat
export const chat = {
  list: () => request('/chat/'),
  create: () => request('/chat/', { method: 'POST' }),
  get: (id) => request(`/chat/${id}/`),
  delete: (id) => request(`/chat/${id}/`, { method: 'DELETE' }),
  send: (id, message) => request(`/chat/${id}/message/`, { method: 'POST', body: JSON.stringify({ message }) }),
  confirm: (messageId) => request(`/chat/messages/${messageId}/confirm/`, { method: 'POST' }),
  cancel: (messageId) => request(`/chat/messages/${messageId}/cancel/`, { method: 'POST' }),
};

// Grocery
export const grocery = {
  list: () => request('/grocery/'),
  current: () => request('/grocery/current/'),
  generate: () => request('/grocery/generate/', { method: 'POST' }),
  done: () => request('/grocery/done/', { method: 'POST' }),
  toggleItem: (listId, itemId) => request(`/grocery/${listId}/items/${itemId}/`, { method: 'PATCH' }),
  updateQuantity: (listId, itemId, quantity) => request(`/grocery/${listId}/items/${itemId}/`, { method: 'PATCH', body: JSON.stringify({ quantity }) }),
  addItem: (listId, name, quantity, category) => request(`/grocery/${listId}/items/add/`, { method: 'POST', body: JSON.stringify({ name, quantity, category }) }),
  deleteItem: (listId, itemId) => request(`/grocery/${listId}/items/${itemId}/delete/`, { method: 'DELETE' }),
  quickAdd: (name, quantity) => request('/grocery/quick-add/', { method: 'POST', body: JSON.stringify({ name, quantity }) }),
};

// Housework
export const housework = {
  current: () => request('/housework/current/'),
  generate: () => request('/housework/generate/', { method: 'POST' }),
  toggleTask: (listId, taskId) => request(`/housework/${listId}/tasks/${taskId}/`, { method: 'PATCH' }),
  addTask: (listId, name) => request(`/housework/${listId}/tasks/add/`, { method: 'POST', body: JSON.stringify({ name }) }),
  deleteTask: (listId, taskId) => request(`/housework/${listId}/tasks/${taskId}/delete/`, { method: 'DELETE' }),
  templates: () => request('/housework/templates/'),
  addTemplate: (name, days) => request('/housework/templates/', { method: 'POST', body: JSON.stringify({ name, days }) }),
  updateTemplate: (id, data) => request(`/housework/templates/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTemplate: (id) => request(`/housework/templates/${id}/`, { method: 'DELETE' }),
};

// Custom sections
export const customSection = {
  current: (key) => request(`/custom-sections/${key}/current/`),
  generate: (key) => request(`/custom-sections/${key}/generate/`, { method: 'POST' }),
  toggleTask: (key, listId, taskId) => request(`/custom-sections/${key}/${listId}/tasks/${taskId}/`, { method: 'PATCH' }),
  addTask: (key, listId, name) => request(`/custom-sections/${key}/${listId}/tasks/add/`, { method: 'POST', body: JSON.stringify({ name }) }),
  deleteTask: (key, listId, taskId) => request(`/custom-sections/${key}/${listId}/tasks/${taskId}/delete/`, { method: 'DELETE' }),
};

// Essentials (new mom)
export const essentials = {
  current: () => request('/essentials/current/'),
  toggle: (checkId) => request(`/essentials/${checkId}/toggle/`, { method: 'PATCH' }),
  add: (item) => request('/essentials/add/', { method: 'POST', body: JSON.stringify({ item }) }),
  remove: (checkId) => request(`/essentials/${checkId}/remove/`, { method: 'DELETE' }),
  markGrocery: (checkId) => request(`/essentials/${checkId}/to-grocery/`, { method: 'PATCH' }),
};

// Pantry
export const pantry = {
  list: () => request('/pantry/'),
  toggle: (name) => request('/pantry/toggle/', { method: 'POST', body: JSON.stringify({ name }) }),
};

// Reminders
export const reminders = {
  list: () => request('/reminders/'),
  upcoming: () => request('/reminders/upcoming/'),
  dismiss: (id) => request(`/reminders/${id}/dismiss/`, { method: 'PATCH' }),
};

// Kids Activities
export const kidsActivities = {
  current: () => request('/kids-activities/current/'),
  markRead: (dayId) => request(`/kids-activities/${dayId}/mark-read/`, { method: 'POST' }),
  downloadUrl: (dayId) => `${API_BASE}/kids-activities/${dayId}/download/`,
};
