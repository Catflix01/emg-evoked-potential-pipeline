function experiment_type = getExperimentType()
    % GETEXPERIMENTTYPE - Prompts the user to enter the experiment type ('hand' or 'foot')
    % Output: 
    %   experiment_type - A string ('hand' or 'foot') based on user input.
    %                     Returns an empty string if the input is invalid or canceled.

    % Define the prompt, title, and input field dimensions
    prompt = {'Is the data for a hand or foot experiment? (Enter "hand" or "foot"):'};
    dlgtitle = 'Experiment Type Input';
    dims = [1 50];  % [height, width] of input field
    definput = {'hand'};  % Optional default value

    % Display the input dialog and get user input
    user_input = inputdlg(prompt, dlgtitle, dims, definput);

    % Check if user cancels the dialog
    if isempty(user_input)
        disp('User cancelled input.');
        experiment_type = '';  % Return empty string if canceled
        return;
    end

    % Extract and validate the input
    experiment_type = lower(user_input{1});  % Ensure lowercase for consistency
    if ~ismember(experiment_type, {'hand', 'foot'})
        warning('Invalid input. Please enter either "hand" or "foot".');
        experiment_type = '';  % Return empty string if input is invalid
    end

    % Display the valid input
    if ~isempty(experiment_type)
        fprintf('Experiment Type: %s\n', experiment_type);
    end
end