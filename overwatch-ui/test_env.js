import dotenv from 'dotenv';
const parsed = dotenv.parse('VITE_API_URL= https://tastiness-antarctic-tassel.ngrok-free.dev');
console.log(parsed);
