%% =======================================================================
%  EMG_Pipeline_Main.m
%  Main script for EMG Analysis Pipeline
%  -----------------------------------------------------------------------
%  Description:
%  This script serves as the main entry point for EMG data analysis.
%  It includes separate sections for configuration, data loading,
%  preprocessing, feature extraction, visualization, and saving results.
%
%  Author: [Mingxiao Liu]
%  Date:   [10/31/2025]
%  Edited: [Lynda Murray; 06/08/2026]
%  =======================================================================

%% Setup
clc; clear; close all;

% Add current folder and subfolders to path
addpath(genpath(pwd));

disp('===================================================');
disp('     EMG Analysis Pipeline - Main Script Started    ');
disp(['     Current Folder: ', pwd]);
disp('===================================================');

%% Section 1: Data Management / Folder Creation
% ------------------------------------------------------
% This section automatically sets up the folder structure
% for the EMG analysis workflow.

disp('--- Section 1: Data Management / Folder Creation ---');

% Prompt user to select the main study folder
mainFolder = uigetdir(pwd, 'Select Main Study Folder');
if mainFolder == 0
    error('No folder selected. Exiting pipeline.');
end

% Define the main data folder
dataMain = fullfile(mainFolder, 'DATA_FOR_PROCESSING');

% Define subfolders
subFolders = { ...
    'ALL-DATA', ...
    'ARCHIVE', ...
    'CODE', ...
    '1.CROSS-CHECK', ...
    '2.PROCESSED-DATA', ...
    '3.REORDER-DATA', ...
    '4.DEMOGRAPHICS', ...
    '5.OTHER-DATA', ...
    '6.CONCATENATED', ...
    '7.CLEAN-DATA', ...
    '8.PRETTY-FIGURES' ...
};

% Create main folder if it doesn’t exist
if ~exist(dataMain, 'dir')
    mkdir(dataMain);
    disp(['Created folder: ', dataMain]);
else
    disp(['Folder already exists: ', dataMain]);
end

% Create all subfolders
for i = 1:numel(subFolders)
    fPath = fullfile(dataMain, subFolders{i});
    if ~exist(fPath, 'dir')
        mkdir(fPath);
        fprintf('Created subfolder: %s\n', subFolders{i});
    else
        fprintf('Subfolder already exists: %s\n', subFolders{i});
    end
end

disp('--- Folder structure setup completed successfully ---');
disp(' ');
