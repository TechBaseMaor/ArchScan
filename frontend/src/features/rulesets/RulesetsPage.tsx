import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Plus, Upload } from 'lucide-react';
import { listRulesets, createRuleset } from '../../shared/api/rulesets';
import { useToast } from '../../shared/components/Toast';
import Modal from '../../shared/components/Modal';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { RuleSet } from '../../shared/api/types';

export default function RulesetsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
  const [showCreate, setShowCreate] = useState(false);
  const [jsonInput, setJsonInput] = useState('');
  const [parseError, setParseError] = useState('');

  const { data: rulesets, isLoading } = useQuery({
    queryKey: ['rulesets'],
    queryFn: listRulesets,
  });

  const createMut = useMutation({
    mutationFn: (rs: RuleSet) => createRuleset(rs),
    onSuccess: (rs) => {
      queryClient.invalidateQueries({ queryKey: ['rulesets'] });
      showSuccess(`Ruleset "${rs.name}" created`);
      setShowCreate(false);
      setJsonInput('');
    },
    onError: () => showError('Failed to create ruleset'),
  });

  const handleSubmit = () => {
    setParseError('');
    try {
      const parsed = JSON.parse(jsonInput);
      if (!parsed.name) {
        setParseError('Ruleset must have a "name" field');
        return;
      }
      createMut.mutate(parsed);
    } catch (e) {
      setParseError('Invalid JSON. Please check syntax.');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setJsonInput(reader.result as string);
    reader.readAsText(file);
  };

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Rulesets</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} style={{ marginRight: 6, verticalAlign: -3 }} />
          New Ruleset
        </button>
      </div>

      {!rulesets?.length ? (
        <EmptyState
          icon={<BookOpen size={48} />}
          message="No rulesets yet. Create your first regulatory ruleset."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Create Ruleset</button>}
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Name</th><th>Version</th><th>Jurisdiction</th><th>Rules</th><th>Effective Date</th></tr>
            </thead>
            <tbody>
              {rulesets.map((rs) => (
                <tr key={rs.ruleset_id} style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/rulesets/${rs.ruleset_id}`)}>
                  <td style={{ fontWeight: 600 }}>{rs.name}</td>
                  <td><span className="badge badge-info">v{rs.version}</span></td>
                  <td>{rs.jurisdiction}</td>
                  <td>{rs.rules.length}</td>
                  <td style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>{rs.effective_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showCreate} onClose={() => { setShowCreate(false); setParseError(''); }} title="Create Ruleset">
        <p style={{ fontSize: 13, color: 'var(--color-text-dim)', marginBottom: 16 }}>
          Paste a ruleset JSON or upload a .json file.
        </p>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="rs-file" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <Upload size={14} /> Upload JSON File
          </label>
          <input id="rs-file" type="file" accept=".json" style={{ display: 'none' }} onChange={handleFileUpload} />
        </div>
        <textarea
          value={jsonInput}
          onChange={(e) => { setJsonInput(e.target.value); setParseError(''); }}
          rows={14}
          placeholder='{"name":"My Rules","jurisdiction":"IL","version":"1.0.0","rules":[...]}'
          style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
        />
        {parseError && <p style={{ color: 'var(--color-error)', fontSize: 13, marginTop: 6 }}>{parseError}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={!jsonInput.trim() || createMut.isPending}>
            {createMut.isPending ? <Spinner size={14} /> : 'Create'}
          </button>
        </div>
      </Modal>
    </>
  );
}
