# README

Sketch-Face is a Discord bot designed to generate likeness images based on an input image of your face! Connects to [PULID via Replicate](https://replicate.com/zsxkib/pulid), so a Replicate account is required to use this. Eventually I would like to make a fully local version once I upgrade my hardware.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Credits System](#credits-system)
- [TODO](#todo)

## Installation

1. **Clone the repository:**

    ```
    git clone <repository_url>
    cd <repository_directory>
    ```

2. **Install dependencies:**

    ```
    pip install -r requirements.txt
    ```

3. **Set up environment variables:**

    Copy or rename the `.env.example` file to `.env` and update the values with your configuration:

    ```
    cp .env.example .env
    ```

    Update the content of the `.env` file:

    ```env
    REPLICATE_API_TOKEN=your_replicate_api_key
    DISCORD_TOKEN=your_discord_bot_token
    ADMIN_ID=your_discord_id
    DEFAULT_NEGATIVE_PROMPT=default_value
    ```

4. **Run the bot:**

    ```
    python bot.py
    ```

## Usage

Once the bot is running, invite it to your Discord server using the invite link generated for your bot. Interact with the bot using commands in any channel where the bot has access.


**Optional Flags:**

- `--seed <value>`: Set a specific seed value for the image generation. Otherwise, a random seed is used.
- `--scale <value>`: Set a specific scale for the image generation (default is 1.2).
- `--no <value>`: Set negative prompts which should not be included in the generation. Overrides the default negative prompt set in the .env.
- `--n <value>`: Set the number of generations (maximum is 4).

**Example:**

```
!sketch "a portrait of a man, cyberpunk style --seed 42"
```
![image](https://github.com/coalescentdivide/sketch-face/assets/6615163/d0492ca7-cd24-4cac-b431-895bfe0018d0)


## Credits System

- Each user starts with an initial balance of 100 credits.
- The cost in credits is dependent on the time it takes for the image generation which is typically 1 credit per image
- Users can check their balance, receive credits from the admin, or gift credits to other users.

### `!balance`

Check your current credit balance.

### `!credit`

Admin command to add credits to a user account.

**Example:**

```
!credit 100 @username
```

### `!gift`

Removes credits from your balance to gift to another user.

**Example:**

```
!gift 50 @username
```


## TODO

- [x] Add wildcard feature
- [x] Set up basic credit system
- [ ] Create local machine version.
