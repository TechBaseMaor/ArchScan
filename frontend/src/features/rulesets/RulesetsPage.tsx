import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Plus, Upload } from 'lucide-react';
import { listRulesets, createRuleset } from '../../shared/api/rulesets';
import { useToast } from '../../shared/components/Toast';
import { useI18n } from '../../shared/i18n';
import Modal from '../../shared/components/Modal';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { RuleSet } from '../../shared/api/types';

export default function RulesetsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
  const { t } = useI18n();
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
      showSuccess(t('rulesets.success', { name: rs.name }));
      setShowCreate(false);
      setJsonInput('');
    },
    onError: () => showError(t('rulesets.error')),
  });

  const handleSubmit = () => {
    setParseError('');
    try {
      const parsed = JSON.parse(jsonInput);
      if (!parsed.name) {
        setParseError(t('rulesets.createModal.nameRequired'));
        return;
      }
      createMut.mutate(parsed);
    } catch {
      setParseError(t('rulesets.createModal.invalidJson'));
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
        <h1>{t('rulesets.title')}</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
          {t('rulesets.new')}
        </button>
      </div>

      {!rulesets?.length ? (
        <EmptyState
          icon={<BookOpen size={48} />}
          message={t('rulesets.empty')}
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>{t('rulesets.createRuleset')}</button>}
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr><th>{t('rulesets.name')}</th><th>{t('rulesets.version')}</th><th>{t('rulesets.jurisdiction')}</th><th>{t('rulesets.rules')}</th><th>{t('rulesets.effectiveDate')}</th></tr>
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
        </div>
      )}

      <Modal open={showCreate} onClose={() => { setShowCreate(false); setParseError(''); }} title={t('rulesets.createModal.title')}>
        <p style={{ fontSize: 13, color: 'var(--color-text-dim)', marginBottom: 16 }}>
          {t('rulesets.createModal.description')}
        </p>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="rs-file" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <Upload size={14} /> {t('rulesets.createModal.uploadJson')}
          </label>
          <input id="rs-file" type="file" accept=".json" style={{ display: 'none' }} onChange={handleFileUpload} />
        </div>
        <textarea
          value={jsonInput}
          onChange={(e) => { setJsonInput(e.target.value); setParseError(''); }}
          rows={14}
          placeholder={t('rulesets.createModal.placeholder')}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
        />
        {parseError && <p style={{ color: 'var(--color-error)', fontSize: 13, marginTop: 6 }}>{parseError}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button className="btn-secondary" onClick={() => setShowCreate(false)}>{t('common.cancel')}</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={!jsonInput.trim() || createMut.isPending}>
            {createMut.isPending ? <Spinner size={14} /> : t('common.create')}
          </button>
        </div>
      </Modal>
    </>
  );
}
