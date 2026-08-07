%% PHARMA Universal EMG Lineup Re-Sorting Script
%  Uses MASTER-UE lineup in "Centralized-NIDAQ-System.xlsx"
%  Adds two columns:
%     "Muscle #": original index based on acquisition lineup
%     "MasterUE #": universal index based on MASTER-UE
%  Then sorts all rows accordingly.
%
%  Written by: Mingxiao
%  Date: 2025-12-05

clear; clc;

%% ========= USER INPUT =========
rootFolder = input('Enter the PHARMA root folder path: ', 's');
if ~isfolder(rootFolder)
    error('Folder does not exist.');
end

fprintf('Root folder: %s\n', rootFolder);

%% ========= Locate AUC and P2P CSVs =========
aucFiles = dir(fullfile(rootFolder, 'AUC_All_Files_All_Muscles*.csv'));
p2pFiles = dir(fullfile(rootFolder, 'P2P_All_Files_All_Muscles*.csv'));

if isempty(aucFiles) && isempty(p2pFiles)
    error('No AUC or P2P combined files found in root folder.');
end

%% ========= Channel (original) lineup (Muscle #) =========
channel_map = {'LTA','RTA','LBB','RBB','LTB','RTB','LFCR', ...
               'RFCR','LECR','RECR','LAPB','RAPB','LFDI','RFDI', ...
               'LADM','RADM','TSS_Trigger','Extra_Channel','TMS_Trigger'};

%% ========= Read MASTER-UE lineup =========
applyMaster = true;
masterFileXLSX = fullfile(rootFolder, 'Centralized-NIDAQ-System.xlsx');
masterFileXLS  = fullfile(rootFolder, 'Centralized-NIDAQ-System.xls');

if isfile(masterFileXLSX)
    masterFile = masterFileXLSX;
elseif isfile(masterFileXLS)
    masterFile = masterFileXLS;
else
    warning('MASTER-UE file not found. Skipping MASTER-UE sorting.');
    applyMaster = false;
end

masterLabels = string.empty;

if applyMaster
    try
        C = readcell(masterFile, 'Sheet', 'MASTER-UE');
        rowIdx = find(strcmp(C(:,1), 'MASTER LINE UP'), 1);

        if isempty(rowIdx)
            warning('MASTER LINE UP row not found. Skipping MASTER-UE sorting.');
            applyMaster = false;
        else
            masterLabels = string(C(rowIdx, 2:22));
            masterLabels = masterLabels(masterLabels ~= "");
        end
    catch ME
        warning('Error reading MASTER-UE: %s. Skipping.', ME.message);
        applyMaster = false;
    end
end

if applyMaster
    % Convert MASTER labels → normalized keys
    masterKeys = arrayfun(@normalizeMuscleName, masterLabels);
    masterIdxMap = containers.Map(masterKeys, num2cell(1:numel(masterKeys)));
else
    masterIdxMap = [];
end

%% ========= Process AUC and P2P similarly =========
processFileList(aucFiles, channel_map, masterIdxMap);
processFileList(p2pFiles, channel_map, masterIdxMap);

fprintf('\n====== Re-sorting complete. All files updated. ======\n');


%% =====================================================================
%% ========================= Helper Functions ==========================
%% =====================================================================

function processFileList(fileList, channel_map, masterIdxMap)
    if isempty(fileList), return; end

    for f = 1:numel(fileList)
        filePath = fullfile(fileList(f).folder, fileList(f).name);
        fprintf('Processing %s\n', filePath);

        T = readtable(filePath);

        % --- Check if already processed
        if ismember('MasterUE #', T.Properties.VariableNames)
            fprintf('Already contains MasterUE # — skipping.\n');
            continue;
        end

        % Extract muscles
        muscles = string(T.Muscle);

        % === Muscle # (original index) ===
        origIdx = zeros(height(T),1);
        for i = 1:height(T)
            loc = find(strcmp(channel_map, muscles(i)));
            if isempty(loc)
                origIdx(i) = NaN;
            else
                origIdx(i) = loc;
            end
        end

        % === MasterUE # (universal index) ===
        masterIdx = zeros(height(T),1);
        for i = 1:height(T)
            key = normalizeMuscleName(muscles(i));
            if isempty(masterIdxMap) || ~isKey(masterIdxMap, key)
                masterIdx(i) = NaN;
            else
                masterIdx(i) = masterIdxMap(key);
            end
        end

        % Insert columns AFTER "Muscle"
        T = addvars(T, origIdx, masterIdx, 'After','Muscle', ...
            'NewVariableNames', {'Muscle #','MasterUE #'});

        % Sort
        if any(~isnan(masterIdx))
            T = sortrows(T, {'Filename','Pulse','MasterUE #'});
        end

        % Overwrite file
        writetable(T, filePath);
        fprintf('  Updated and saved.\n');
    end
end


function key = normalizeMuscleName(lbl)
    % Convert to canonical key
    if isempty(lbl)
        key = "";
        return;
    end

    s = char(lbl);
    s = strtrim(s);
    s = strrep(s, '*', '');  % remove stars

    % Special rule: bare "PINCH" => treat as "PINCH (BK)"
    if strcmpi(strtrim(s), 'PINCH')
        s = 'PINCH (BK)';
    end

    % Remove spaces + ()
    s = regexprep(s, '\s+', '');
    s = regexprep(s, '[()]', '');

    key = upper(string(s));
end
