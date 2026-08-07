% PHARMA EMG Batch: per-experiment analysis + global concatenation
% written by Mingxiao Liu
% 08/26/2025

%% Batch driver
clear; close all; clc;
tic

% ---- PHARMA root ----
rootPath = input('Enter the PHARMA root folder path: ', 's');
allDataDir = fullfile(rootPath, 'ALL-DATA');
if ~isfolder(allDataDir), error('Folder does not exist.'); end
fprintf('Root path: %s\n', rootPath);
addpath(genpath(allDataDir));

% ---- Ask once: response vs pre-stim ----
data_type = getDataType();
if isempty(data_type), error('No valid data type selected.'); end
fprintf('Data type selected: %s\n', data_type);

% ---- Walk subjects -> experiments -> _TMS ----
subjects = dir(fullfile(allDataDir, 'P1S*'));   % one folder per participant
subjects = subjects([subjects.isdir]);

for s = 1:numel(subjects)
    subjFolder = fullfile(allDataDir, subjects(s).name);
    fprintf('\n=== Subject: %s ===\n', subjects(s).name);

        tmsDirs = dir(fullfile(subjFolder, '**', '*_TMS'));
        tmsDirs = tmsDirs([tmsDirs.isdir]);

        for k = 1:numel(tmsDirs)
            tmsPath = fullfile(tmsDirs(k).folder, tmsDirs(k).name);
            fprintf('Found TMS folder: %s\n', tmsPath);
            % ---- run your existing per-experiment analysis here ----
            run_emg_analysis(tmsPath, data_type);
        end

end

% ---- After all experiments, concatenate everything ----
fprintf('\n=== Concatenating all experiment results ===\n');
concat_results(rootPath, data_type);

toc
disp('All done ✅');

%% ============================
%% Local function: per-experiment analysis
function run_emg_analysis(folderPath, data_type)
    % Per-experiment analysis. Inserts E# into AnalysisResults_* names
    % right after subject (P1Sxx) and before VxTx, so later plots can parse E#.

    % Find CSVs for this experiment
    disp(folderPath)
    disp(isfolder(folderPath))
    dir(folderPath)
    filePattern = fullfile(folderPath, 'P1S*.csv');
    allFiles = dir(filePattern);

    % Exclude REC_full_data
    csvFiles = allFiles(~contains({allFiles.name}, 'REC_full_data', 'IgnoreCase', true));

    if isempty(csvFiles)
        fprintf('No analysis CSV files in %s\n', folderPath);
        return;
    end

    % Pull E# from the experiment path (e.g., ...\<subject>_V4E1_<date>\...\<subject>_V4E1_TMS)
    eTok = regexp(folderPath, 'E(\d+)', 'tokens', 'once');
    if ~isempty(eTok)
        eStr = ['E' eTok{1}];   % e.g., 'E1'
    else
        eStr = 'E?';            % fallback if not found
        warning('Could not find E# in path: %s', folderPath);
    end

    % channel map for this protocol
    channel_map = {'LTA','RTA','LBB','RBB','LTB','RTB','LFCR', ...
                   'RFCR','LECR','RECR','LAPB','RAPB','LFDI','RFDI', ...
                   'LADM','RADM','TSS_Trigger','Extra_Channel','TMS_Trigger'};
    numVars = numel(channel_map);
    Var_map = arrayfun(@(x) sprintf('Var%d', x), 1:numVars, 'UniformOutput', false);

    Fs = 5000; % Hz

    for k = 1:numel(csvFiles)
        baseFileName = csvFiles(k).name;
        fullFileName = fullfile(folderPath, baseFileName);
        fprintf('   Analyzing: %s\n', fullFileName);

        T = readtable(fullFileName, 'VariableNamingRule','preserve');

        % Parse filename parts: P1Sxx_V4T0_RAPB_TMS_120_...
        stem = erase(baseFileName, '.csv');
        parts = split(stem, '_');

        % Expected at least: [P1Sxx, VxTx, Target, TMS|TSS, ...]
        if numel(parts) < 3
            warning('Filename %s unexpected; skipping.', baseFileName);
            continue;
        end
        subjTok   = string(parts{1});  % e.g. 'P1Sxx'
        vtTok     = string(parts{2});  % 'V4T0'
        stimTok   = upper(string(parts{4})); % 'TMS' or 'TSS' (if present)

        % Construct an output stem with E# inserted after subject and before VxTx
        % Result: P1Sxx_E1_V4T0_... (if E# found)
        % Keep rest of tokens the same order
        if numel(parts) >= 3
            % Insert eStr right after subjTok
            partsOut = [subjTok; string(eStr); parts(2:end)];
        else
            partsOut = [subjTok; string(eStr); vtTok];
        end
        outStemWithE = strjoin(partsOut, '_');

        % Pick trigger channel
        if stimTok == "TSS"
            trigVar = 'Var17'; % TSS_Trigger
        elseif any(stimTok == ["TMS","IMM"])
            trigVar = 'Var19'; % TMS_Trigger
        else
            warning('Not TMS/TSS (%s); skipping file.', stimTok);
            continue;
        end
        if ~ismember(trigVar, T.Properties.VariableNames)
            warning('Missing trigger var %s in %s; skipping.', trigVar, baseFileName);
            continue;
        end

        Trigger_Channel = T.(trigVar);
        if istable(Trigger_Channel), Trigger_Channel = table2array(Trigger_Channel); end
        if ~isnumeric(Trigger_Channel), Trigger_Channel = str2double(string(Trigger_Channel)); end

        % Trigger index (pairs -> take first)
        idxTrig = find(Trigger_Channel > 5);
        if isempty(idxTrig)
            warning('No trigger >5 found in %s; skipping.', baseFileName);
            continue;
        end
        maskFirst = [true; diff(idxTrig) > 1];
        idxSingle = idxTrig(maskFirst);
        num_trials = numel(idxSingle);

        % Pre-allocate
        num_muscles = numel(channel_map);
        AUC_matrix           = zeros(num_trials, num_muscles);
        P2P_matrix           = zeros(num_trials, num_muscles);
        AUC_matrix_preStim   = zeros(num_trials, num_muscles);
        P2P_matrix_preStim   = zeros(num_trials, num_muscles);

        % Loop muscles
        for m = 1:num_muscles
            vname = Var_map{m};
            if ~ismember(vname, T.Properties.VariableNames)
                warning('Missing %s in %s', vname, baseFileName);
                continue;
            end
            x = T.(vname);
            if istable(x), x = table2array(x); end
            if ~isnumeric(x), x = str2double(string(x)); end

            for i = 1:num_trials
                % trial windows
                if i == num_trials
                    seg  = x( idxSingle(i) - round(0.200*Fs) : idxSingle(i) + round(0.075*Fs) ); %#ok<NASGU>
                else
                    seg  = x( idxSingle(i) - round(0.200*Fs) : idxSingle(i) + round(0.500*Fs) ); %#ok<NASGU>
                end
                pre  = x( idxSingle(i) - round(0.100*Fs) : idxSingle(i) - round(0.050*Fs) );
                resp = x( idxSingle(i) + round(0.010*Fs) : idxSingle(i) + round(0.070*Fs) );

                % metrics
                P2P_matrix(i,m)         = peak2peak(resp);
                AUC_matrix(i,m)         = trapz(abs(resp));
                P2P_matrix_preStim(i,m) = peak2peak(pre);
                AUC_matrix_preStim(i,m) = trapz(abs(pre));
            end
        end

        % Write per-experiment results (with E# inserted)
        % Build output stem with E# already inserted (you already have outStemWithE)
        outStemClean = regexprep(string(outStemWithE), "[^\w]", "_");           % ensure string scalar, clean non-word chars
        outDirName   = "AnalysisResults_" + outStemClean;                        % <- single string scalar
        outDir       = fullfile(folderPath, char(outDirName));                   % mkdir accepts char or string scalar
        if ~isfolder(outDir), mkdir(outDir); end

        rowNames = strcat('Pulse_', string(1:num_trials));
        if data_type == "response"
            aucT = array2table(num2cell(AUC_matrix), 'VariableNames', channel_map, 'RowNames', cellstr(rowNames));
            p2pT = array2table(num2cell(P2P_matrix), 'VariableNames', channel_map, 'RowNames', cellstr(rowNames));
            writetable(aucT, fullfile(outDir,'AUC_All_Muscles.csv'), 'WriteRowNames', true);
            writetable(p2pT, fullfile(outDir,'P2P_All_Muscles.csv'), 'WriteRowNames', true);
        else
            aucT = array2table(num2cell(AUC_matrix_preStim), 'VariableNames', channel_map, 'RowNames', cellstr(rowNames));
            p2pT = array2table(num2cell(P2P_matrix_preStim), 'VariableNames', channel_map, 'RowNames', cellstr(rowNames));
            writetable(aucT, fullfile(outDir,'AUC_All_Muscles_preStim.csv'), 'WriteRowNames', true);
            writetable(p2pT, fullfile(outDir,'P2P_All_Muscles_preStim.csv'), 'WriteRowNames', true);
        end
    end
end


%% ============================
%% Local function: global concatenation
function concat_results(rootFolder, data_type)
    % Collect all AnalysisResults_* folders recursively and stack into tall CSVs

    % --- Determine filenames to find
    if data_type == "response"
        aucName = 'AUC_All_Muscles.csv';
        p2pName = 'P2P_All_Muscles.csv';
        outAUC  = 'AUC_All_Files_All_Muscles.csv';
        outP2P  = 'P2P_All_Files_All_Muscles.csv';
    else
        aucName = 'AUC_All_Muscles_preStim.csv';
        p2pName = 'P2P_All_Muscles_preStim.csv';
        outAUC  = 'AUC_All_Files_All_Muscles_preStim.csv';
        outP2P  = 'P2P_All_Files_All_Muscles_preStim.csv';
    end

    % --- Define the channel map (must match your analysis order)
    channel_map = {'LTA','RTA','LBB','RBB','LTB','RTB','LFCR', ...
                   'RFCR','LECR','RECR','LAPB','RAPB','LFDI','RFDI', ...
                   'LADM','RADM','TSS_Trigger','Extra_Channel','TMS_Trigger'};

    % --- Find all AnalysisResults_* folders recursively
    resDirs = dir(fullfile(rootFolder, '**', 'AnalysisResults_*'));
    resDirs = resDirs([resDirs.isdir]);
    if isempty(resDirs)
        warning('No AnalysisResults_* folders found under %s', rootFolder);
        return;
    end

    combAUC = table();
    combP2P = table();

    for d = 1:numel(resDirs)
        R = fullfile(resDirs(d).folder, resDirs(d).name);

        % ---- AUC ----
        fA = fullfile(R, aucName);
        if isfile(fA)
            T = readtable(fA, 'ReadRowNames', true, 'VariableNamingRule','preserve');

            % Extract pulse labels
            if ~isempty(T.Properties.RowNames)
                pulse = string(T.Properties.RowNames);
            elseif ismember('Row', T.Properties.VariableNames)
                pulse = string(T.Row); T.Row = [];
            else
                firstVars = T.Properties.VariableNames;
                maybePulse = string(T.(firstVars{1}));
                if all(startsWith(maybePulse,"Pulse_"))
                    pulse = maybePulse; T(:,1) = [];
                else
                    pulse = "Pulse_" + string((1:height(T)).');
                end
            end

            % Wide -> long
            muscles = T.Properties.VariableNames;
            for j = 1:numel(muscles)
                col = T.(muscles{j});
                % --- Add muscle index ---
                muscleNum = find(strcmp(channel_map, muscles{j}));
                if isempty(muscleNum), muscleNum = NaN; end
                combAUC = [combAUC; table( ...
                    repmat({resDirs(d).name}, height(T), 1), ...
                    pulse, ...
                    repmat(string(muscles{j}), height(T), 1), ...
                    repmat(muscleNum, height(T), 1), ...
                    col, ...
                    'VariableNames', {'Filename','Pulse','Muscle','Muscle #','AUC'})]; %#ok<AGROW>
            end
        end

        % ---- P2P ----
        fP = fullfile(R, p2pName);
        if isfile(fP)
            T = readtable(fP, 'ReadRowNames', true, 'VariableNamingRule','preserve');
            if ~isempty(T.Properties.RowNames)
                pulse = string(T.Properties.RowNames);
            elseif ismember('Row', T.Properties.VariableNames)
                pulse = string(T.Row); T.Row = [];
            else
                firstVars = T.Properties.VariableNames;
                maybePulse = string(T.(firstVars{1}));
                if all(startsWith(maybePulse,"Pulse_"))
                    pulse = maybePulse; T(:,1) = [];
                else
                    pulse = "Pulse_" + string((1:height(T)).');
                end
            end

            muscles = T.Properties.VariableNames;
            for j = 1:numel(muscles)
                col = T.(muscles{j});
                muscleNum = find(strcmp(channel_map, muscles{j}));
                if isempty(muscleNum), muscleNum = NaN; end
                combP2P = [combP2P; table( ...
                    repmat({resDirs(d).name}, height(T), 1), ...
                    pulse, ...
                    repmat(string(muscles{j}), height(T), 1), ...
                    repmat(muscleNum, height(T), 1), ...
                    col, ...
                    'VariableNames', {'Filename','Pulse','Muscle','Muscle #','P2P'})]; %#ok<AGROW>
            end
        end
    end

    % ---- Write combined tables ----
    if ~isempty(combAUC)
        writetable(combAUC, fullfile(rootFolder, outAUC));
        fprintf('Wrote %s\n', fullfile(rootFolder, outAUC));
    else
        warning('No AUC files found to concatenate.');
    end

    if ~isempty(combP2P)
        writetable(combP2P, fullfile(rootFolder, outP2P));
        fprintf('Wrote %s\n', fullfile(rootFolder, outP2P));
    else
        warning('No P2P files found to concatenate.');
    end
end
