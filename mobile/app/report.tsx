import { useState } from 'react'
import { useRouter } from 'expo-router'
import { Pressable, SafeAreaView, StyleSheet, Text, TextInput } from 'react-native'
import { api } from '../src/api'

export default function ReportScreen() {
  const router = useRouter()
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    setSaving(true); setMessage('')
    try { await api('/waste-reports/', { method: 'POST', body: JSON.stringify({ waste_type: 'other', description, location }) }); router.back() }
    catch (error) { setMessage((error as Error).message) }
    finally { setSaving(false) }
  }
  return <SafeAreaView style={styles.screen}><Text style={styles.title}>Report waste</Text><TextInput style={styles.input} placeholder="Describe the waste" value={description} onChangeText={setDescription} multiline /><TextInput style={styles.input} placeholder="Location" value={location} onChangeText={setLocation} /><Text style={styles.error}>{message}</Text><Pressable style={styles.button} disabled={saving || !description || !location} onPress={submit}><Text style={styles.buttonText}>{saving ? 'Submitting...' : 'Submit report'}</Text></Pressable></SafeAreaView>
}

const styles = StyleSheet.create({ screen: { flex: 1, padding: 24, backgroundColor: '#f5f7f3' }, title: { color: '#17221d', fontSize: 28, fontWeight: '700', marginBottom: 24 }, input: { backgroundColor: '#fff', borderColor: '#dce4de', borderWidth: 1, marginBottom: 14, padding: 14, minHeight: 52 }, error: { color: '#963e2a', minHeight: 24 }, button: { backgroundColor: '#1f6b4d', padding: 14, alignItems: 'center' }, buttonText: { color: '#fff', fontWeight: '700' } })
