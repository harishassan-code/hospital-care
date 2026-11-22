import { Button } from '../../components/form/Button'
import { Panel } from '../../components/ui/Panel'
import { CommandCentreBoard } from '../../features/commandCentre/CommandCentre'
import { useCommandCentre } from '../../features/commandCentre/useCommandCentre'

/** City command centre (story #55): the whole network's figures for admins, read-only, refreshed every minute. */
export default function CommandCentrePage() {
  const { state, retry } = useCommandCentre()

  if (state.kind === 'loading') return <p role="status">Loading the network’s figures…</p>
  if (state.kind === 'failed') {
    return (
      <Panel title="Network figures">
        <p role="alert">The network’s figures couldn’t be loaded. The hospital’s system didn’t respond.</p>
        <Button type="button" onClick={retry}>
          Try again
        </Button>
      </Panel>
    )
  }
  return <CommandCentreBoard figures={state.figures} stale={state.stale} />
}
