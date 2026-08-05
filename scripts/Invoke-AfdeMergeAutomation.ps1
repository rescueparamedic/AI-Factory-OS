[CmdletBinding()]
param(
    [string]$Repository,
    [int]$PullRequestNumber,
    [string]$BaseBranch,
    [string]$ExpectedBaseSha,
    [string]$HeadBranch,
    [string]$ExpectedHeadSha,
    [switch]$WorkAuditPassed,
    [switch]$ChatMergePassed,
    [switch]$UserMergeApproved
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-SafePropertyValue {
    param(
        [AllowNull()][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][object]$DefaultValue = $null
    )

    if ($null -eq $InputObject) {
        return $DefaultValue
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $DefaultValue
    }
    return $property.Value
}

function ConvertTo-NativeArgument {
    param([AllowEmptyString()][string]$Value)

    if ($Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes += 1
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append((('\' * (($backslashes * 2) + 1)) -join ''))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append((('\' * $backslashes) -join ''))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append((('\' * ($backslashes * 2)) -join ''))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$Arguments = @(),
        [scriptblock]$Executor
    )

    if ($null -ne $Executor) {
        $execution = & $Executor $Command ([string[]]$Arguments)
    }
    else {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $Command
        $startInfo.Arguments = (($Arguments | ForEach-Object {
                    ConvertTo-NativeArgument -Value $_
                }) -join ' ')
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        try {
            if (-not $process.Start()) {
                throw "Native command could not be started: $Command"
            }
            $stdoutTask = $process.StandardOutput.ReadToEndAsync()
            $stderrTask = $process.StandardError.ReadToEndAsync()
            $process.WaitForExit()
            $execution = [pscustomobject]@{
                ExitCode = $process.ExitCode
                StdOut = $stdoutTask.Result
                StdErr = $stderrTask.Result
            }
        }
        finally {
            $process.Dispose()
        }
    }

    $exitCode = Get-SafePropertyValue -InputObject $execution -Name 'ExitCode'
    $stdout = [string](Get-SafePropertyValue -InputObject $execution -Name 'StdOut' -DefaultValue '')
    $stderr = [string](Get-SafePropertyValue -InputObject $execution -Name 'StdErr' -DefaultValue '')
    if ($null -eq $exitCode) {
        throw "Native command executor returned no exit code: $Command"
    }
    if ([int]$exitCode -ne 0) {
        $rendered = (@($Command) + $Arguments) -join ' '
        throw "Native command failed: $rendered`nExit code: $exitCode`nstdout:`n$stdout`nstderr:`n$stderr"
    }
    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        StdOut = $stdout
        StdErr = $stderr
    }
}

function Invoke-NativeText {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$Arguments = @(),
        [scriptblock]$Executor
    )

    $result = Invoke-NativeCommand -Command $Command -Arguments $Arguments -Executor $Executor
    return $result.StdOut.Trim()
}

function ConvertTo-NormalizedCheck {
    param([Parameter(Mandatory = $true)][object]$Check)

    $name = $null
    foreach ($propertyName in @('name', 'context', 'workflowName')) {
        $candidate = Get-SafePropertyValue -InputObject $Check -Name $propertyName
        if (-not [string]::IsNullOrWhiteSpace([string]$candidate)) {
            $name = [string]$candidate
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = '<unnamed>'
    }

    $status = [string](Get-SafePropertyValue -InputObject $Check -Name 'status' -DefaultValue '')
    $conclusion = [string](Get-SafePropertyValue -InputObject $Check -Name 'conclusion' -DefaultValue '')
    $state = [string](Get-SafePropertyValue -InputObject $Check -Name 'state' -DefaultValue '')
    $status = $status.ToUpperInvariant()
    $conclusion = $conclusion.ToUpperInvariant()
    $state = $state.ToUpperInvariant()

    $pendingStates = @('EXPECTED', 'PENDING', 'QUEUED', 'REQUESTED', 'IN_PROGRESS', 'WAITING')
    $successStates = @('SUCCESS', 'SKIPPED', 'NEUTRAL')
    $effectiveState = $state
    if (-not [string]::IsNullOrWhiteSpace($conclusion)) {
        $effectiveState = $conclusion
    }
    elseif (-not [string]::IsNullOrWhiteSpace($status)) {
        $effectiveState = $status
    }

    if ($pendingStates -contains $status -or $pendingStates -contains $effectiveState) {
        $category = 'PENDING'
    }
    elseif ($successStates -contains $effectiveState) {
        $category = 'SUCCESS'
    }
    else {
        $category = 'FAILURE'
    }

    return [pscustomobject]@{
        Name = $name
        State = $effectiveState
        Category = $category
    }
}

function Assert-CiChecks {
    param([AllowNull()][object[]]$Checks)

    $normalized = @($Checks | ForEach-Object { ConvertTo-NormalizedCheck -Check $_ })
    if ($normalized.Count -eq 0) {
        throw 'No CI checks were reported; merge fails closed.'
    }
    $pending = @($normalized | Where-Object { $_.Category -eq 'PENDING' })
    if ($pending.Count -gt 0) {
        throw "CI checks are still in progress: $(($pending.Name) -join ', ')"
    }
    $failed = @($normalized | Where-Object { $_.Category -eq 'FAILURE' })
    if ($failed.Count -gt 0) {
        throw "CI checks did not succeed: $(($failed.Name) -join ', ')"
    }
    return $normalized
}

function Get-MergeRecoveryPlan {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('OPEN', 'MERGED')][string]$PrState,
        [bool]$IsDraft,
        [bool]$LocalBranchExists,
        [bool]$RemoteBranchExists,
        [bool]$DevelopSynchronized
    )

    return [pscustomobject]@{
        ShouldMarkReady = ($PrState -eq 'OPEN' -and $IsDraft)
        ShouldMerge = ($PrState -eq 'OPEN')
        ShouldSynchronizeDevelop = (-not $DevelopSynchronized)
        ShouldDeleteLocalBranch = $LocalBranchExists
        ShouldDeleteRemoteBranch = $RemoteBranchExists
    }
}

function Assert-InputContract {
    param(
        [string]$RepositoryValue,
        [int]$PrNumberValue,
        [string]$BaseBranchValue,
        [string]$BaseShaValue,
        [string]$HeadBranchValue,
        [string]$HeadShaValue,
        [bool]$WorkPassed,
        [bool]$ChatPassed,
        [bool]$UserApproved
    )

    if ($RepositoryValue -notmatch '^[^/\s]+/[^/\s]+$') {
        throw 'Repository must use the owner/name form.'
    }
    if ($PrNumberValue -le 0) {
        throw 'PullRequestNumber must be positive.'
    }
    if ([string]::IsNullOrWhiteSpace($BaseBranchValue) -or
        [string]::IsNullOrWhiteSpace($HeadBranchValue) -or
        $BaseBranchValue -eq $HeadBranchValue) {
        throw 'BaseBranch and HeadBranch must be distinct non-empty names.'
    }
    if ($BaseShaValue -notmatch '^[0-9a-fA-F]{40}$' -or
        $HeadShaValue -notmatch '^[0-9a-fA-F]{40}$') {
        throw 'Expected Base and Head SHAs must be full 40-character hexadecimal values.'
    }
    if (-not ($WorkPassed -and $ChatPassed -and $UserApproved)) {
        throw 'Work PASS, Chat Merge PASS, and explicit user Merge approval are all required.'
    }
}

function Get-PullRequestSnapshot {
    param(
        [string]$RepositoryValue,
        [int]$PrNumberValue,
        [scriptblock]$Executor
    )

    $json = Invoke-NativeText -Command 'gh' -Arguments @(
        'pr', 'view', [string]$PrNumberValue, '--repo', $RepositoryValue,
        '--json', 'state,isDraft,baseRefName,baseRefOid,headRefName,headRefOid,mergeable,statusCheckRollup,mergeCommit'
    ) -Executor $Executor
    try {
        return $json | ConvertFrom-Json
    }
    catch {
        throw 'GitHub CLI returned malformed pull request JSON.'
    }
}

function Assert-PullRequestSnapshot {
    param(
        [Parameter(Mandatory = $true)][object]$Snapshot,
        [string]$BaseBranchValue,
        [string]$BaseShaValue,
        [string]$HeadBranchValue,
        [string]$HeadShaValue
    )

    $state = ([string](Get-SafePropertyValue $Snapshot 'state' '')).ToUpperInvariant()
    if (@('OPEN', 'MERGED') -notcontains $state) {
        throw "Pull request state is not mergeable or recoverable: $state"
    }
    if ([string](Get-SafePropertyValue $Snapshot 'baseRefName' '') -ne $BaseBranchValue) {
        throw 'Pull request base branch does not match the expected input.'
    }
    if ([string](Get-SafePropertyValue $Snapshot 'baseRefOid' '') -ne $BaseShaValue) {
        throw 'Pull request base SHA does not match the expected input.'
    }
    if ([string](Get-SafePropertyValue $Snapshot 'headRefName' '') -ne $HeadBranchValue) {
        throw 'Pull request head branch does not match the expected input.'
    }
    if ([string](Get-SafePropertyValue $Snapshot 'headRefOid' '') -ne $HeadShaValue) {
        throw 'Pull request head SHA does not match the expected input.'
    }
    if ($state -eq 'OPEN') {
        $mergeable = ([string](Get-SafePropertyValue $Snapshot 'mergeable' '')).ToUpperInvariant()
        if ($mergeable -ne 'MERGEABLE') {
            throw "Pull request is not mergeable: $mergeable"
        }
    }
    $checks = @(Get-SafePropertyValue $Snapshot 'statusCheckRollup' @())
    [void](Assert-CiChecks -Checks $checks)
    return $state
}

function Get-MergeCommitSha {
    param([Parameter(Mandatory = $true)][object]$Snapshot)

    $mergeCommit = Get-SafePropertyValue $Snapshot 'mergeCommit'
    $mergeCommitSha = [string](Get-SafePropertyValue $mergeCommit 'oid' '')
    if ($mergeCommitSha -notmatch '^[0-9a-fA-F]{40}$') {
        throw 'Merged pull request has no valid merge commit SHA.'
    }
    return $mergeCommitSha
}

function Assert-MergeCommitMethod {
    param(
        [Parameter(Mandatory = $true)][string]$MergeCommitSha,
        [Parameter(Mandatory = $true)][string]$ExpectedBaseSha,
        [Parameter(Mandatory = $true)][string]$ExpectedHeadSha,
        [scriptblock]$Executor
    )

    $commitLine = Invoke-NativeText 'git' @(
        'rev-list', '--parents', '-n', '1', $MergeCommitSha
    ) $Executor
    $commitAndParents = @($commitLine -split '\s+' | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        })
    if ($commitAndParents.Count -ne 3 -or
        $commitAndParents[0] -ne $MergeCommitSha -or
        $commitAndParents[1] -ne $ExpectedBaseSha -or
        $commitAndParents[2] -ne $ExpectedHeadSha) {
        throw 'Pull request was not merged with the required Merge Commit method.'
    }
}

function Invoke-AfdeMergeAutomation {
    param(
        [string]$RepositoryValue,
        [int]$PrNumberValue,
        [string]$BaseBranchValue,
        [string]$BaseShaValue,
        [string]$HeadBranchValue,
        [string]$HeadShaValue,
        [bool]$WorkPassed,
        [bool]$ChatPassed,
        [bool]$UserApproved,
        [scriptblock]$Executor
    )

    Assert-InputContract $RepositoryValue $PrNumberValue $BaseBranchValue $BaseShaValue `
        $HeadBranchValue $HeadShaValue $WorkPassed $ChatPassed $UserApproved

    $actualRepository = Invoke-NativeText 'gh' @('repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner') $Executor
    if ($actualRepository -ne $RepositoryValue) {
        throw "Repository mismatch: expected $RepositoryValue, found $actualRepository"
    }
    $initialStatus = Invoke-NativeText 'git' @('status', '--porcelain') $Executor
    if (-not [string]::IsNullOrWhiteSpace($initialStatus)) {
        throw 'Working tree must be clean before merge automation starts.'
    }

    [void](Invoke-NativeCommand 'git' @('fetch', 'origin', $BaseBranchValue) $Executor)
    $snapshot = Get-PullRequestSnapshot $RepositoryValue $PrNumberValue $Executor
    $state = Assert-PullRequestSnapshot $snapshot $BaseBranchValue $BaseShaValue $HeadBranchValue $HeadShaValue
    $wasAlreadyMerged = ($state -eq 'MERGED')
    $wasAlreadyReady = -not [bool](Get-SafePropertyValue $snapshot 'isDraft' $true)
    $entryPlan = Get-MergeRecoveryPlan $state `
        ([bool](Get-SafePropertyValue $snapshot 'isDraft' $false)) `
        $false $false $false

    if ($entryPlan.ShouldMerge) {
        $originBaseSha = Invoke-NativeText 'git' @('rev-parse', "refs/remotes/origin/$BaseBranchValue") $Executor
        if ($originBaseSha -ne $BaseShaValue) {
            throw 'origin base SHA does not match the expected pre-merge SHA.'
        }

        if ($entryPlan.ShouldMarkReady) {
            [void](Invoke-NativeCommand 'gh' @('pr', 'ready', [string]$PrNumberValue, '--repo', $RepositoryValue) $Executor)
            $snapshot = Get-PullRequestSnapshot $RepositoryValue $PrNumberValue $Executor
            $state = Assert-PullRequestSnapshot $snapshot $BaseBranchValue $BaseShaValue $HeadBranchValue $HeadShaValue
            if ([bool](Get-SafePropertyValue $snapshot 'isDraft' $true)) {
                throw 'Pull request remained Draft after the Ready transition.'
            }
        }

        [void](Invoke-NativeCommand 'gh' @('pr', 'merge', [string]$PrNumberValue, '--repo', $RepositoryValue, '--merge') $Executor)
        $snapshot = Get-PullRequestSnapshot $RepositoryValue $PrNumberValue $Executor
        $state = Assert-PullRequestSnapshot $snapshot $BaseBranchValue $BaseShaValue $HeadBranchValue $HeadShaValue
        if ($state -ne 'MERGED') {
            throw 'Pull request did not reach the MERGED state.'
        }
    }

    $mergeCommitSha = Get-MergeCommitSha $snapshot
    [void](Invoke-NativeCommand 'git' @('fetch', 'origin', $BaseBranchValue) $Executor)
    Assert-MergeCommitMethod $mergeCommitSha $BaseShaValue $HeadShaValue $Executor
    [void](Invoke-NativeCommand 'git' @('checkout', $BaseBranchValue) $Executor)
    [void](Invoke-NativeCommand 'git' @('pull', '--ff-only', 'origin', $BaseBranchValue) $Executor)

    $localBaseSha = Invoke-NativeText 'git' @('rev-parse', 'HEAD') $Executor
    $originBaseSha = Invoke-NativeText 'git' @('rev-parse', "refs/remotes/origin/$BaseBranchValue") $Executor
    if ($localBaseSha -ne $originBaseSha) {
        throw 'Local and origin base branches are not synchronized.'
    }
    [void](Invoke-NativeCommand 'git' @('merge-base', '--is-ancestor', $mergeCommitSha, $localBaseSha) $Executor)

    $remoteBranch = Invoke-NativeText 'git' @('ls-remote', '--heads', 'origin', "refs/heads/$HeadBranchValue") $Executor
    $remoteBranchExists = -not [string]::IsNullOrWhiteSpace($remoteBranch)
    $localBranch = Invoke-NativeText 'git' @('branch', '--list', '--format=%(refname:short)', '--', $HeadBranchValue) $Executor
    $localBranchExists = -not [string]::IsNullOrWhiteSpace($localBranch)
    $cleanupPlan = Get-MergeRecoveryPlan 'MERGED' $false `
        $localBranchExists $remoteBranchExists $true
    if ($cleanupPlan.ShouldDeleteRemoteBranch) {
        [void](Invoke-NativeCommand 'git' @('push', 'origin', '--delete', $HeadBranchValue) $Executor)
        $remoteBranch = Invoke-NativeText 'git' @('ls-remote', '--heads', 'origin', "refs/heads/$HeadBranchValue") $Executor
        if (-not [string]::IsNullOrWhiteSpace($remoteBranch)) {
            throw 'Remote feature branch still exists after deletion.'
        }
        $remoteBranchStatus = 'DELETED'
    }
    else {
        $remoteBranchStatus = 'ALREADY_ABSENT'
    }

    if ($cleanupPlan.ShouldDeleteLocalBranch) {
        [void](Invoke-NativeCommand 'git' @('branch', '-d', $HeadBranchValue) $Executor)
        $localBranch = Invoke-NativeText 'git' @('branch', '--list', '--format=%(refname:short)', '--', $HeadBranchValue) $Executor
        if (-not [string]::IsNullOrWhiteSpace($localBranch)) {
            throw 'Local feature branch still exists after deletion.'
        }
        $localBranchStatus = 'DELETED'
    }
    else {
        $localBranchStatus = 'ALREADY_ABSENT'
    }

    $finalStatus = Invoke-NativeText 'git' @('status', '--porcelain') $Executor
    if (-not [string]::IsNullOrWhiteSpace($finalStatus)) {
        throw 'Working tree is not clean after merge automation.'
    }
    $finalLocalSha = Invoke-NativeText 'git' @('rev-parse', 'HEAD') $Executor
    $finalOriginSha = Invoke-NativeText 'git' @('rev-parse', "refs/remotes/origin/$BaseBranchValue") $Executor
    if ($finalLocalSha -ne $finalOriginSha) {
        throw 'Final local and origin base SHAs do not match.'
    }

    $result = [ordered]@{
        Result = 'SUCCESS'
        Repository = $RepositoryValue
        PullRequestNumber = $PrNumberValue
        PullRequestState = 'MERGED'
        MergeMethod = 'MERGE_COMMIT'
        MergeCommitSha = $mergeCommitSha
        BaseBranch = $BaseBranchValue
        BaseSha = $finalLocalSha
        HeadBranch = $HeadBranchValue
        RemoteBranch = $remoteBranchStatus
        LocalBranch = $localBranchStatus
        WasAlreadyMerged = $wasAlreadyMerged
        WasAlreadyReady = $wasAlreadyReady
        WorkingTreeClean = $true
    }
    return $result | ConvertTo-Json -Depth 5
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-AfdeMergeAutomation `
        -RepositoryValue $Repository `
        -PrNumberValue $PullRequestNumber `
        -BaseBranchValue $BaseBranch `
        -BaseShaValue $ExpectedBaseSha `
        -HeadBranchValue $HeadBranch `
        -HeadShaValue $ExpectedHeadSha `
        -WorkPassed $WorkAuditPassed.IsPresent `
        -ChatPassed $ChatMergePassed.IsPresent `
        -UserApproved $UserMergeApproved.IsPresent
}
