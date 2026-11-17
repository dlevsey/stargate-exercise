<!--v004-->
# Stargate

***

## Astronaut Career Tracking System (ACTS)

ACTS is used as a tool to maintain a record of all the People that have served as Astronauts. When serving as an Astronaut, your *Job* (Duty) is tracked by your Rank, Title and the Start and End Dates of the Duty.

The People that exist in this system are not all Astronauts. ACTS maintains a master list of People and Duties that are updated from an external service (not controlled by ACTS). The update schedule is determined by the external service.

## Definitions

1. A person's astronaut assignment is the Astronaut Duty.
1. A person's current astronaut information is stored in the Astronaut Detail table.
1. A person's list of astronaut assignments is stored in the Astronaut Duty table.

## Requirements

##### Enhance the Stargate API (Required)

The REST API is expected to do the following:

1. Retrieve a person by name.
1. Retrieve all people.
1. Add/update a person by name.
1. Retrieve Astronaut Duty by name.
1. Add an Astronaut Duty.

##### Implement a user interface: (Encouraged)

The UI is expected to do the following:

1. Successfully implement a web application that demonstrates production level quality. Angular is preferred.
1. Implement call(s) to retrieve an individual's astronaut duties.
1. Display the progress of the process and the results in a visually sophisticated and appealing manner.

## Tasks

Overview
Examine the code, find and resolve any flaws, if any exist. Identify design patterns and follow or change them. Provide fix(es) and be prepared to describe the changes.

1. Generate the database
   * This is your source and storage location
1. Enforce the rules
1. Improve defensive coding
1. Add unit tests
   * identify the most impactful methods requiring tests
   * reach >50% code coverage
1. Implement process logging
   * Log exceptions
   * Log successes
   * Store the logs in the database

## Rules

1. A Person is uniquely identified by their Name.
1. A Person who has not had an astronaut assignment will not have Astronaut records.
1. A Person will only ever hold one current Astronaut Duty Title, Start Date, and Rank at a time.
1. A Person's Current Duty will not have a Duty End Date.
1. A Person's Previous Duty End Date is set to the day before the New Astronaut Duty Start Date when a new Astronaut Duty is received for a Person.
1. A Person is classified as 'Retired' when a Duty Title is 'RETIRED'.
1. A Person's Career End Date is one day before the Retired Duty Start Date.

## Running this solution

Run every command from the `exercise1` folder. You need the .NET SDK 8 or newer, and the EF Core command-line tool in version 8 (`dotnet tool install --global dotnet-ef --version 8.*`).

1. Create the database. This makes the SQLite file `api\starbase.db` with all tables:

   ```
   cd api
   dotnet ef database update
   ```

2. Run the API (still in `api`), then open http://localhost:5204/swagger in a browser:

   ```
   dotnet run --launch-profile http
   ```

3. Run the tests (from `exercise1`):

   ```
   dotnet test
   ```

   The same with code coverage. The settings file leaves the generated migration files out of the count:

   ```
   dotnet test --collect:"XPlat Code Coverage" --settings coverlet.runsettings
   ```

What was changed, and why, is in [CHANGES.md](CHANGES.md).
