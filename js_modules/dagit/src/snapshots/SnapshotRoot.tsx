import * as React from 'react';
import {Route, RouteComponentProps, Switch} from 'react-router-dom';

import {PipelineExplorerSnapshotRoot} from '../pipelines/PipelineExplorerRoot';
import {explorerPathFromString} from '../pipelines/PipelinePathUtils';
import {PipelineRunsRoot} from '../pipelines/PipelineRunsRoot';

import {SnapshotNav} from './SnapshotNav';

export const SnapshotRoot: React.FC<RouteComponentProps<{pipelinePath: string; tab?: string}>> = (
  props,
) => {
  const {pipelinePath, tab} = props.match.params;
  const explorerPath = explorerPathFromString(pipelinePath);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        width: '100%',
        height: '100%',
      }}
    >
      <SnapshotNav activeTab={tab} explorerPath={explorerPath} />
      <Switch>
        <Route
          path="/instance/snapshots/:pipelinePath/runs"
          render={(props: RouteComponentProps<{pipelinePath: string}>) => (
            <PipelineRunsRoot pipelinePath={props.match.params.pipelinePath} />
          )}
        />
        <Route path="/instance/snapshots/(/?.*)" component={PipelineExplorerSnapshotRoot} />
      </Switch>
    </div>
  );
};
